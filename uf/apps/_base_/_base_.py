import collections

from ...third import tf
from .. import util


class BaseEncoder:
    def __init__(self, *args, **kwargs):
        pass

    def get_pooled_output(self):
        raise NotImplementedError()

    def get_sequence_output(self):
        raise NotImplementedError()


class BaseDecoder:
    def __init__(self, *args, **kwargs):

        # scalar of total loss, used for back propagation
        self.train_loss = None

        # supervised tensors of each example
        self._tensors = collections.OrderedDict()

    def get_forward_outputs(self):
        return (self.train_loss, self._tensors)


class ClsDecoder(BaseDecoder):
    def __init__(
        self,
        is_training,
        input_tensor,
        label_ids,
        is_logits=False,
        label_size=2,
        sample_weight=None,
        scope="cls",
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        trainable=True,
        **kwargs,
    ):
        super().__init__(**kwargs)

        if is_logits:
            logits = input_tensor
        else:
            hidden_size = input_tensor.shape.as_list()[-1]
            with tf.variable_scope(scope):
                output_weights = tf.get_variable(
                    "output_weights",
                    shape=[label_size, hidden_size],
                    initializer=util.create_initializer(initializer_range),
                    trainable=trainable,
                )
                output_bias = tf.get_variable(
                    "output_bias",
                    shape=[label_size],
                    initializer=tf.zeros_initializer(),
                    trainable=trainable,
                )
                output_layer = util.dropout(input_tensor, hidden_dropout_prob if is_training else 0.0)
                logits = tf.matmul(output_layer, output_weights, transpose_b=True)
                logits = tf.nn.bias_add(logits, output_bias)

        self._tensors["preds"] = tf.argmax(logits, axis=-1, name="preds")
        self._tensors["probs"] = tf.nn.softmax(logits, axis=-1, name="probs")

        log_probs = tf.nn.log_softmax(logits, axis=-1)
        one_hot_labels = tf.one_hot(label_ids, depth=label_size, dtype=tf.float32)
        per_example_loss = - tf.reduce_sum(one_hot_labels * log_probs, axis=-1)
        if sample_weight is not None:
            per_example_loss = tf.cast(sample_weight, dtype=tf.float32) * per_example_loss
        thresh = kwargs.get("conf_thresh")
        if thresh is not None:
            assert isinstance(thresh, float), "`conf_thresh` must be a float between 0 and 1."
            largest_prob = tf.reduce_max(tf.exp(log_probs), axis=-1)
            per_example_loss = tf.cast(tf.less(largest_prob, thresh), dtype=tf.float32) * per_example_loss

        self._tensors["losses"] = per_example_loss
        self.train_loss = tf.reduce_mean(per_example_loss)


class RegDecoder(BaseDecoder):
    def __init__(
        self,
        is_training,
        input_tensor,
        label_floats,
        is_logits=False,
        label_size=2,
        sample_weight=None,
        scope="reg",
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        trainable=True,
        **kwargs,
    ):
        super().__init__(**kwargs)

        if is_logits:
            logits = is_logits
        else:
            with tf.variable_scope(scope):
                intermediate_output = tf.layers.dense(
                    input_tensor,
                    label_size * 4,
                    use_bias=False,
                    kernel_initializer=util.create_initializer(initializer_range),
                    trainable=trainable,
                )
                logits = tf.layers.dense(
                    intermediate_output,
                    label_size,
                    use_bias=False,
                    kernel_initializer=util.create_initializer(initializer_range),
                    trainable=trainable,
                    name="preds",
                )

        self._tensors["preds"] = logits

        per_example_loss = tf.reduce_sum(tf.square(label_floats - logits), axis=-1)
        if sample_weight is not None:
            per_example_loss = tf.cast(sample_weight, dtype=tf.float32) * per_example_loss

        self._tensors["losses"] = per_example_loss
        self.train_loss = tf.reduce_mean(per_example_loss)


class BinaryClsDecoder(BaseDecoder):
    def __init__(
        self,
        is_training,
        input_tensor,
        label_ids,
        is_logits=False,
        label_size=2,
        sample_weight=None,
        label_weight=None,
        scope="cls/seq_relationship",
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        trainable=True,
        **kwargs,
    ):
        super().__init__(**kwargs)

        if is_logits:
            logits = input_tensor
        else:
            hidden_size = input_tensor.shape.as_list()[-1]
            with tf.variable_scope(scope):
                output_weights = tf.get_variable(
                    "output_weights",
                    shape=[label_size, hidden_size],
                    initializer=util.create_initializer(initializer_range),
                    trainable=trainable,
                )
                output_bias = tf.get_variable(
                    "output_bias",
                    shape=[label_size],
                    initializer=tf.zeros_initializer(),
                    trainable=trainable,
                )
                output_layer = util.dropout(input_tensor, hidden_dropout_prob if is_training else 0.0)
                logits = tf.matmul(output_layer, output_weights, transpose_b=True)
                logits = tf.nn.bias_add(logits, output_bias)
            
        probs = tf.nn.sigmoid(logits, name="probs")
        self._tensors["probs"] = probs
        self._tensors["preds"] = tf.greater(probs, 0.5, name="preds")

        per_label_loss = tf.nn.sigmoid_cross_entropy_with_logits(logits=logits, labels=tf.cast(label_ids, dtype=tf.float32))
        if label_weight is not None:
            label_weight = tf.constant(label_weight, dtype=tf.float32)
            label_weight = tf.reshape(label_weight, [1, label_size])
            per_label_loss *= label_weight
        per_example_loss = tf.reduce_sum(per_label_loss, axis=-1)
        if sample_weight is not None:
            per_example_loss *= sample_weight

        self._tensors["losses"] = per_example_loss
        self.train_loss = tf.reduce_mean(per_example_loss)


class SeqClsDecoder(BaseDecoder):
    def __init__(
        self,
        is_training,
        input_tensor,
        input_mask,
        label_ids,
        is_logits=False,
        label_size=2,
        sample_weight=None,
        scope="cls/sequence",
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        trainable=True,
        **kwargs,
    ):
        super().__init__(**kwargs)

        if is_logits:
            logits = input_tensor
        else:
            shape = input_tensor.shape.as_list()
            seq_length = shape[-2]
            hidden_size = shape[-1]
            with tf.variable_scope(scope):
                output_weights = tf.get_variable(
                    "output_weights",
                    shape=[label_size, hidden_size],
                    initializer=util.create_initializer(initializer_range),
                    trainable=trainable,
                )
                output_bias = tf.get_variable(
                    "output_bias",
                    shape=[label_size],
                    initializer=tf.zeros_initializer(),
                    trainable=trainable,
                )
                output_layer = util.dropout(input_tensor, hidden_dropout_prob if is_training else 0.0)
                output_layer = tf.reshape(output_layer, [-1, hidden_size])
                logits = tf.matmul(output_layer, output_weights, transpose_b=True)
                logits = tf.nn.bias_add(logits, output_bias)
                logits = tf.reshape(logits, [-1, seq_length, label_size])

        self._tensors["preds"] = tf.argmax(logits, axis=-1, name="preds")
        self._tensors["probs"] = tf.nn.softmax(logits, axis=-1, name="probs")

        log_probs = tf.nn.log_softmax(logits, axis=-1)
        one_hot_labels = tf.one_hot(label_ids, depth=label_size, dtype=tf.float32)
        per_token_loss = - tf.reduce_sum(one_hot_labels * log_probs, axis=-1)
        input_mask = tf.cast(input_mask, tf.float32)
        per_token_loss *= input_mask / tf.reduce_sum(input_mask, keepdims=True, axis=-1)
        per_example_loss = tf.reduce_sum(per_token_loss, axis=-1)
        if sample_weight is not None:
            per_example_loss *= tf.cast(sample_weight, dtype=tf.float32)

        self._tensors["losses"] = per_example_loss
        self.train_loss = tf.reduce_mean(per_example_loss)


class SeqClsCrossDecoder(BaseDecoder):
    def __init__(
        self,
        is_training,
        input_tensor,
        input_mask,
        seq_cls_label_ids,
        cls_label_ids,
        is_logits=False,
        seq_cls_label_size=2,
        cls_label_size=2,
        sample_weight=None,
        seq_cls_scope="cls/tokens",
        cls_scope="cls/sequence",
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        trainable=True,
        **kwargs,
    ):
        super().__init__(**kwargs)

        assert not is_logits, "%s does not support logits convertion right now." % self.__class__.__name__

        shape = input_tensor.shape.as_list()
        seq_length = shape[-2]
        hidden_size = shape[-1]

        # seq cls
        with tf.variable_scope(seq_cls_scope):
            output_weights = tf.get_variable(
                "output_weights",
                shape=[seq_cls_label_size, hidden_size],
                initializer=util.create_initializer(initializer_range),
                trainable=trainable,
            )
            output_bias = tf.get_variable(
                "output_bias",
                shape=[seq_cls_label_size],
                initializer=tf.zeros_initializer(),
                trainable=trainable,
            )
            output_layer = util.dropout(input_tensor, hidden_dropout_prob if is_training else 0.0)
            output_layer = tf.reshape(output_layer, [-1, hidden_size])
            logits = tf.matmul(output_layer, output_weights, transpose_b=True)
            logits = tf.nn.bias_add(logits, output_bias)
            logits = tf.reshape(logits, [-1, seq_length, seq_cls_label_size])
            self._tensors["seq_cls_preds"] = tf.argmax(logits, axis=-1, name="seq_cls_preds")
            self._tensors["seq_cls_probs"] = tf.nn.softmax(logits, axis=-1, name="seq_cls_probs")
            log_probs = tf.nn.log_softmax(logits, axis=-1)
            one_hot_labels = tf.one_hot(seq_cls_label_ids, depth=seq_cls_label_size, dtype=tf.float32)
            per_token_loss = - tf.reduce_sum(one_hot_labels * log_probs, axis=-1)
            input_mask = tf.cast(input_mask, tf.float32)
            per_token_loss *= input_mask / tf.reduce_sum(input_mask, keepdims=True, axis=-1)
            per_example_loss = tf.reduce_sum(per_token_loss, axis=-1)
            if sample_weight is not None:
                per_example_loss *= tf.cast(sample_weight, dtype=tf.float32)
            self._tensors["seq_cls_losses"] = per_example_loss

        # cls
        with tf.variable_scope(cls_scope):
            output_weights = tf.get_variable(
                "output_weights",
                shape=[cls_label_size, hidden_size],
                initializer=util.create_initializer(initializer_range),
                trainable=trainable,
            )
            output_bias = tf.get_variable(
                "output_bias",
                shape=[cls_label_size],
                initializer=tf.zeros_initializer(),
                trainable=trainable,
            )
            output_layer = util.dropout(input_tensor, hidden_dropout_prob if is_training else 0.0)
            logits = tf.matmul(output_layer[:,0,:], output_weights, transpose_b=True)
            logits = tf.nn.bias_add(logits, output_bias)
            self._tensors["cls_preds"] = tf.argmax(logits, axis=-1, name="cls_preds")
            self._tensors["cls_probs"] = tf.nn.softmax(logits, axis=-1, name="cls_probs")
            log_probs = tf.nn.log_softmax(logits, axis=-1)
            one_hot_labels = tf.one_hot(cls_label_ids, depth=cls_label_size, dtype=tf.float32)
            per_example_loss = - tf.reduce_sum(one_hot_labels * log_probs, axis=-1)
            if sample_weight is not None:
                per_example_loss = tf.cast(sample_weight, dtype=tf.float32) * per_example_loss
            self._tensors["cls_losses"] = per_example_loss

        self.train_loss = tf.reduce_mean(self._tensors["seq_cls_losses"]) + tf.reduce_mean(self._tensors["cls_losses"])


class MRCDecoder(BaseDecoder):
    def __init__(
        self,
        is_training,
        input_tensor,
        label_ids,
        is_logits=False,
        sample_weight=None,
        scope="mrc",
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        trainable=True,
        **kwargs,
    ):
        super().__init__(**kwargs)

        if is_logits:
            logits = input_tensor
        else:
            seq_length = input_tensor.shape.as_list()[-2]
            hidden_size = input_tensor.shape.as_list()[-1]
            with tf.variable_scope(scope):
                output_weights = tf.get_variable(
                    "output_weights",
                    shape=[2, hidden_size],
                    initializer=util.create_initializer(initializer_range),
                    trainable=trainable,
                )
                output_bias = tf.get_variable(
                    "output_bias",
                    shape=[2],
                    initializer=tf.zeros_initializer(),
                    trainable=trainable,
                )
                output_layer = util.dropout(input_tensor, hidden_dropout_prob if is_training else 0.0)
                output_layer = tf.reshape(output_layer, [-1, hidden_size])
                logits = tf.matmul(output_layer, output_weights, transpose_b=True)
                logits = tf.nn.bias_add(logits, output_bias)
                logits = tf.reshape(logits, [-1, seq_length, 2])
                logits = tf.transpose(logits, [0, 2, 1])

        probs = tf.nn.softmax(logits, axis=-1, name="probs")
        self._tensors["probs"] = probs
        self._tensors["preds"] = tf.argmax(logits, axis=-1, name="preds")

        start_one_hot_labels = tf.one_hot(label_ids[:, 0], depth=seq_length, dtype=tf.float32)
        end_one_hot_labels = tf.one_hot(label_ids[:, 1], depth=seq_length, dtype=tf.float32)
        start_log_probs = tf.nn.log_softmax(logits[:, 0, :], axis=-1)
        end_log_probs = tf.nn.log_softmax(logits[:, 1, :], axis=-1)
        per_example_loss = (
            - 0.5 * tf.reduce_sum(start_one_hot_labels * start_log_probs, axis=-1)
            - 0.5 * tf.reduce_sum(end_one_hot_labels * end_log_probs, axis=-1)
        )
        if sample_weight is not None:
            per_example_loss *= sample_weight

        self._tensors["losses"] = per_example_loss
        self.train_loss = tf.reduce_mean(per_example_loss)