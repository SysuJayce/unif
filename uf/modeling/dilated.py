# coding:=utf-8
# Copyright 2021 Tencent. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
''' Dilated language modeling. '''

from ..tools import tf
from .base import BaseDecoder
from .bert import BERTEncoder
from . import util


class DLM(BaseDecoder, BERTEncoder):
    def __init__(self,
                 bert_config,
                 is_training,
                 dilated_ids,
                 label_ids,
                 max_seq_length,
                 spad_id=1,
                 loop=3,
                 sample_weight=None,
                 scope='dilated',
                 use_tilda_embedding=False,
                 **kwargs):
        super().__init__()

        # Tilda embeddings for SMART algorithm
        tilda_embeddings = None
        if use_tilda_embedding:
            with tf.variable_scope('', reuse=True):
                tilda_embeddings = tf.get_variable('tilda_embeddings')

        dilated_mask = tf.cast(
            tf.not_equal(dilated_ids, 0), tf.float32)

        shape = util.get_shape_list(dilated_ids, expected_rank=2)
        batch_size = shape[0]
        dilated_seq_length = shape[1]

        with tf.variable_scope(scope):

            # forward once
            if is_training:
                logits = self._bert_forward(
                    bert_config,
                    dilated_ids,
                    dilated_mask,
                    batch_size,
                    dilated_seq_length,
                    tilda_embeddings=tilda_embeddings)

                self._preds['LM'] = tf.argmax(logits, axis=-1)

                # LM loss
                log_probs = tf.nn.log_softmax(logits, axis=-1)
                one_hot_labels = tf.one_hot(
                    label_ids, depth=bert_config.vocab_size)
                per_token_loss = -tf.reduce_sum(
                    one_hot_labels * log_probs, axis=-1)

                input_length = tf.reduce_sum(
                    dilated_mask, axis=-1) * 2
                label_mask = tf.sequence_mask(
                    input_length, max_seq_length * 2, dtype=tf.float32)
                per_example_loss = \
                    tf.reduce_sum(per_token_loss * label_mask, axis=-1) / \
                    tf.reduce_sum(label_mask, axis=-1)
                if sample_weight is not None:
                    per_example_loss *= tf.expand_dims(sample_weight, axis=-1)

                self.total_loss = tf.reduce_mean(per_example_loss)
                self._losses['LM'] = per_example_loss

            # forward loop
            else:
                def _forward(dilated_ids, dilated_mask):

                    logits = self._bert_forward(
                        bert_config,
                        dilated_ids,
                        dilated_mask,
                        batch_size,
                        dilated_seq_length,
                        tilda_embeddings=tilda_embeddings)
                    output_ids = tf.argmax(logits, axis=-1)
                    output_ids = tf.cast(output_ids, dtype=tf.int32)

                    # special padding (using `spad` token)
                    equal_zero = tf.cast(tf.equal(output_ids, 0), tf.int32)
                    equal_zero = tf.reduce_sum(equal_zero, axis=-1)
                    right_pad = spad_id * tf.sequence_mask(
                        equal_zero, dilated_seq_length, dtype=tf.int32)
                    paded = tf.concat([output_ids, right_pad], axis=-1)

                    # extract ids of length `max_seq_length`
                    flattened_padded = tf.reshape(paded, [-1])
                    is_valid = tf.cast(
                        tf.greater(flattened_padded, 0), dtype=tf.int32)
                    flattened_valid = tf.boolean_mask(
                        flattened_padded, is_valid)
                    valid = tf.reshape(
                        flattened_valid, [batch_size, dilated_seq_length])
                    cutted_valid = valid[:, :max_seq_length]

                    # replace `spad` token with `pad`
                    non_spad_mask = tf.cast(
                        tf.not_equal(cutted_valid, spad_id), dtype=tf.int32)
                    output_ids = cutted_valid * non_spad_mask
                    output_length = tf.reduce_sum(non_spad_mask, axis=-1)

                    # dilate
                    reshaped_ids = tf.reshape(
                        output_ids, [batch_size, max_seq_length, 1])
                    reshaped_mask = tf.reshape(
                        tf.sequence_mask(output_length, max_seq_length,
                                         dtype=tf.int32),
                        [batch_size, max_seq_length, 1])
                    concat_ids = tf.concat(
                        [reshaped_ids, tf.zeros_like(reshaped_ids)], axis=-1)
                    concat_mask = tf.concat(
                        [reshaped_mask, tf.zeros_like(
                            reshaped_mask, dtype=tf.int32)],
                         axis=-1)
                    dilated_ids = tf.reshape(
                        concat_ids, [batch_size, max_seq_length * 2])
                    dilated_mask = tf.reshape(
                        concat_mask, [batch_size, max_seq_length * 2])

                    return dilated_ids, dilated_mask

                for _ in range(loop):
                    dilated_ids, dilated_mask = _forward(
                        dilated_ids, dilated_mask)

                self._preds['LM'] = dilated_ids

    def _bert_forward(self,
                     bert_config,
                     input_ids,
                     input_mask,
                     batch_size,
                     dilated_seq_length,
                     dtype=tf.float32,
                     trainable=True,
                     tilda_embeddings=None):

        with tf.variable_scope('embeddings'):

            (embedding_output, embedding_table) = self.embedding_lookup(
                input_ids=input_ids,
                vocab_size=bert_config.vocab_size,
                batch_size=batch_size,
                max_seq_length=dilated_seq_length,
                embedding_size=bert_config.hidden_size,
                initializer_range=bert_config.initializer_range,
                word_embedding_name='word_embeddings',
                dtype=dtype,
                trainable=trainable,
                tilda_embeddings=tilda_embeddings)

            # Add positional embeddings and token type embeddings
            # layer normalize and perform dropout.
            embedding_output = self.embedding_postprocessor(
                input_tensor=embedding_output,
                batch_size=batch_size,
                max_seq_length=dilated_seq_length,
                hidden_size=bert_config.hidden_size,
                use_token_type=False,
                use_position_embeddings=True,
                position_embedding_name='position_embeddings',
                initializer_range=bert_config.initializer_range,
                max_position_embeddings=\
                    bert_config.max_position_embeddings,
                dropout_prob=bert_config.hidden_dropout_prob,
                dtype=dtype,
                trainable=trainable)

        with tf.variable_scope('encoder'):
            attention_mask = self.create_attention_mask_from_input_mask(
                input_mask, batch_size, dilated_seq_length, dtype=dtype)

            # stacked transformers
            all_encoder_layers = self.transformer_model(
                input_tensor=embedding_output,
                batch_size=batch_size,
                max_seq_length=dilated_seq_length,
                attention_mask=attention_mask,
                hidden_size=bert_config.hidden_size,
                num_hidden_layers=bert_config.num_hidden_layers,
                num_attention_heads=bert_config.num_attention_heads,
                intermediate_size=bert_config.intermediate_size,
                intermediate_act_fn=util.get_activation(
                    bert_config.hidden_act),
                hidden_dropout_prob=bert_config.hidden_dropout_prob,
                attention_probs_dropout_prob=\
                bert_config.attention_probs_dropout_prob,
                initializer_range=bert_config.initializer_range,
                dtype=dtype,
                trainable=trainable)

        flattened = tf.reshape(
            all_encoder_layers[-1],
            [batch_size * dilated_seq_length, bert_config.hidden_size])
        logits = tf.matmul(flattened, embedding_table, transpose_b=True)
        logits = tf.reshape(
            logits, [-1, dilated_seq_length, bert_config.vocab_size])

        return logits

    def create_attention_mask_from_input_mask(self,
                                              input_mask,
                                              batch_size,
                                              max_seq_length,
                                              dtype=tf.float32):
        to_mask = tf.cast(tf.reshape(
            input_mask, [batch_size, 1, max_seq_length]), dtype=dtype)
        broadcast_ones = tf.ones(
            shape=[batch_size, max_seq_length, 1], dtype=dtype)
        mask = broadcast_ones * to_mask

        broadcast_eye = tf.tile(
            tf.reshape(tf.eye(max_seq_length), [1, max_seq_length, max_seq_length]),
            [batch_size, 1, 1])
        mask += broadcast_eye
        mask = tf.cast(tf.greater(mask, 0), dtype)
        return mask
