import numpy as np

from .base import ClassifierModule, MRCModule, LMModule
from .bert import BERTClassifier, BERTBinaryClassifier, BERTSeqClassifier, BERTMRC, BERTLM
from ..model.base import ClsDecoder, BinaryClsDecoder, SeqClsDecoder, MRCDecoder
from ..model.bert import BERTEncoder, BERTConfig, create_masked_lm_predictions, get_decay_power
from ..model.electra import ELECTRA
from ..token import WordPieceTokenizer
from ..third import tf
from .. import com


class ELECTRAClassifier(BERTClassifier, ClassifierModule):
    """ Single-label classifier on ELECTRA. """
    _INFER_ATTRIBUTES = BERTClassifier._INFER_ATTRIBUTES

    def __init__(
        self,
        config_file,
        vocab_file,
        max_seq_length=128,
        label_size=None,
        init_checkpoint=None,
        output_dir=None,
        gpu_ids=None,
        do_lower_case=True,
        truncate_method="LIFO",
    ):
        self.__init_args__ = locals()
        super(ClassifierModule, self).__init__(init_checkpoint, output_dir, gpu_ids)

        self.batch_size = 0
        self.max_seq_length = max_seq_length
        self.label_size = label_size
        self.truncate_method = truncate_method
        self._id_to_label = None

        self.bert_config = BERTConfig.from_json_file(config_file)
        self.tokenizer = WordPieceTokenizer(vocab_file, do_lower_case)
        self.decay_power = get_decay_power(self.bert_config.num_hidden_layers)

        if "[CLS]" not in self.tokenizer.vocab:
            self.tokenizer.add("[CLS]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[CLS]` into vocabulary.")
        if "[SEP]" not in self.tokenizer.vocab:
            self.tokenizer.add("[SEP]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[SEP]` into vocabulary.")

    def _forward(self, is_training, split_placeholders, **kwargs):

        encoder = BERTEncoder(
            bert_config=self.bert_config,
            is_training=is_training,
            input_ids=split_placeholders["input_ids"],
            input_mask=split_placeholders["input_mask"],
            segment_ids=split_placeholders["segment_ids"],
            scope="electra",
            drop_pooler=True,
            **kwargs,
        )
        encoder_output = encoder.get_pooled_output()
        decoder = ClsDecoder(
            is_training=is_training,
            input_tensor=encoder_output,
            label_ids=split_placeholders["label_ids"],
            label_size=self.label_size,
            sample_weight=split_placeholders.get("sample_weight"),
            scope="cls/seq_relationship",
            **kwargs,
        )
        return decoder.get_forward_outputs()


class ELECTRABinaryClassifier(BERTBinaryClassifier, ClassifierModule):
    """ Multi-label classifier on ELECTRA. """
    _INFER_ATTRIBUTES = BERTBinaryClassifier._INFER_ATTRIBUTES

    def __init__(
        self,
        config_file,
        vocab_file,
        max_seq_length=128,
        label_size=None,
        label_weight=None,
        init_checkpoint=None,
        output_dir=None,
        gpu_ids=None,
        do_lower_case=True,
        truncate_method="LIFO",
    ):
        self.__init_args__ = locals()
        super(ClassifierModule, self).__init__(init_checkpoint, output_dir, gpu_ids)

        self.batch_size = 0
        self.max_seq_length = max_seq_length
        self.label_size = label_size
        self.label_weight = label_weight
        self.truncate_method = truncate_method
        self._id_to_label = None

        self.bert_config = BERTConfig.from_json_file(config_file)
        self.tokenizer = WordPieceTokenizer(vocab_file, do_lower_case)
        self.decay_power = get_decay_power(self.bert_config.num_hidden_layers)

        if "[CLS]" not in self.tokenizer.vocab:
            self.tokenizer.add("[CLS]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[CLS]` into vocabulary.")
        if "[SEP]" not in self.tokenizer.vocab:
            self.tokenizer.add("[SEP]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[SEP]` into vocabulary.")

    def _forward(self, is_training, split_placeholders, **kwargs):

        encoder = BERTEncoder(
            bert_config=self.bert_config,
            is_training=is_training,
            input_ids=split_placeholders["input_ids"],
            input_mask=split_placeholders["input_mask"],
            segment_ids=split_placeholders["segment_ids"],
            scope="electra",
            drop_pooler=True,
            **kwargs,
        )
        encoder_output = encoder.get_pooled_output()
        decoder = BinaryClsDecoder(
            is_training=is_training,
            input_tensor=encoder_output,
            label_ids=split_placeholders["label_ids"],
            label_size=self.label_size,
            sample_weight=split_placeholders.get("sample_weight"),
            label_weight=self.label_weight,
            scope="cls/seq_relationship",
            **kwargs,
        )
        return decoder.get_forward_outputs()


class ELECTRASeqClassifier(BERTSeqClassifier, ClassifierModule):
    """ Sequence labeling classifier on ELECTRA. """
    _INFER_ATTRIBUTES = BERTSeqClassifier._INFER_ATTRIBUTES

    def __init__(
        self,
        config_file,
        vocab_file,
        max_seq_length=128,
        label_size=None,
        init_checkpoint=None,
        output_dir=None,
        gpu_ids=None,
        do_lower_case=True,
        truncate_method="LIFO",
    ):
        self.__init_args__ = locals()
        super(ClassifierModule, self).__init__(init_checkpoint, output_dir, gpu_ids)

        self.batch_size = 0
        self.max_seq_length = max_seq_length
        self.label_size = label_size
        self.truncate_method = truncate_method
        self._id_to_label = None

        self.bert_config = BERTConfig.from_json_file(config_file)
        self.tokenizer = WordPieceTokenizer(vocab_file, do_lower_case)
        self.decay_power = get_decay_power(self.bert_config.num_hidden_layers)

        if "[CLS]" not in self.tokenizer.vocab:
            self.tokenizer.add("[CLS]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[CLS]` into vocabulary.")
        if "[SEP]" not in self.tokenizer.vocab:
            self.tokenizer.add("[SEP]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[SEP]` into vocabulary.")

    def _forward(self, is_training, split_placeholders, **kwargs):

        encoder = BERTEncoder(
            bert_config=self.bert_config,
            is_training=is_training,
            input_ids=split_placeholders["input_ids"],
            input_mask=split_placeholders["input_mask"],
            segment_ids=split_placeholders["segment_ids"],
            scope="electra",
            drop_pooler=True,
            **kwargs,
        )
        encoder_output = encoder.get_sequence_output()
        decoder = SeqClsDecoder(
            is_training=is_training,
            input_tensor=encoder_output,
            input_mask=split_placeholders["input_mask"],
            label_ids=split_placeholders["label_ids"],
            label_size=self.label_size,
            sample_weight=split_placeholders.get("sample_weight"),
            scope="cls/sequence",
            **kwargs,
        )
        return decoder.get_forward_outputs()


class ELECTRAMRC(BERTMRC, MRCModule):
    """ Machine reading comprehension on ELECTRA. """
    _INFER_ATTRIBUTES = BERTMRC._INFER_ATTRIBUTES

    def __init__(
        self,
        config_file,
        vocab_file,
        max_seq_length=256,
        init_checkpoint=None,
        output_dir=None,
        gpu_ids=None,
        do_lower_case=True,
        truncate_method="longer-FO",
    ):
        self.__init_args__ = locals()
        super(MRCModule, self).__init__(init_checkpoint, output_dir, gpu_ids)

        self.batch_size = 0
        self.max_seq_length = max_seq_length
        self.truncate_method = truncate_method
        self._do_lower_case = do_lower_case
        self._on_predict = False
        self._id_to_label = None

        self.bert_config = BERTConfig.from_json_file(config_file)
        self.tokenizer = WordPieceTokenizer(vocab_file, do_lower_case)
        self.decay_power = get_decay_power(self.bert_config.num_hidden_layers)

        if "[CLS]" not in self.tokenizer.vocab:
            self.tokenizer.add("[CLS]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[CLS]` into vocabulary.")
        if "[SEP]" not in self.tokenizer.vocab:
            self.tokenizer.add("[SEP]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[SEP]` into vocabulary.")

    def _forward(self, is_training, split_placeholders, **kwargs):

        encoder = BERTEncoder(
            bert_config=self.bert_config,
            is_training=is_training,
            input_ids=split_placeholders["input_ids"],
            input_mask=split_placeholders["input_mask"],
            segment_ids=split_placeholders["segment_ids"],
            scope="electra",
            drop_pooler=True,
            **kwargs,
        )
        encoder_output = encoder.get_sequence_output()
        decoder = MRCDecoder(
            is_training=is_training,
            input_tensor=encoder_output,
            label_ids=split_placeholders["label_ids"],
            sample_weight=split_placeholders.get("sample_weight"),
            scope="mrc",
            **kwargs,
        )
        return decoder.get_forward_outputs()


class ELECTRALM(BERTLM, LMModule):
    """ Language modeling on ELECTRA. """
    _INFER_ATTRIBUTES = BERTLM._INFER_ATTRIBUTES

    def __init__(
        self,
        vocab_file,
        model_size="base",
        max_seq_length=128,
        init_checkpoint=None,
        output_dir=None,
        gpu_ids=None,
        generator_weight=1.0,
        discriminator_weight=50.0,
        max_predictions_per_seq=20,
        masked_lm_prob=0.15,
        do_whole_word_mask=False,
        do_lower_case=True,
        truncate_method="LIFO",
    ):
        self.__init_args__ = locals()
        super(LMModule, self).__init__(init_checkpoint, output_dir, gpu_ids)

        self.batch_size = 0
        self.max_seq_length = max_seq_length
        self.generator_weight = generator_weight
        self.discriminator_weight = discriminator_weight
        self.masked_lm_prob = masked_lm_prob
        self.do_whole_word_mask = do_whole_word_mask
        self.truncate_method = truncate_method
        self._model_size = model_size
        self._max_predictions_per_seq = max_predictions_per_seq
        self._id_to_label = None

        self.tokenizer = WordPieceTokenizer(vocab_file, do_lower_case)
        self.decay_power = "unsupported"

        if "[CLS]" not in self.tokenizer.vocab:
            self.tokenizer.add("[CLS]")
            tf.logging.info("Add necessary token `[CLS]` into vocabulary.")
        if "[SEP]" not in self.tokenizer.vocab:
            self.tokenizer.add("[SEP]")
            tf.logging.info("Add necessary token `[SEP]` into vocabulary.")

    def convert(self, X=None, y=None, sample_weight=None, X_tokenized=None, is_training=False, is_parallel=False):
        self._assert_legal(X, y, sample_weight, X_tokenized)

        assert y is None, "Training of %s is unsupervised. `y` should be None." % self.__class__.__name__

        n_inputs = None
        data = {}

        # convert X
        if X or X_tokenized:
            tokenized = False if X else X_tokenized

            (input_ids, input_mask, segment_ids,
             masked_lm_positions, masked_lm_ids, masked_lm_weights) = self._convert_X(X_tokenized if tokenized else X, is_training, tokenized=tokenized)

            data["input_ids"] = np.array(input_ids, dtype=np.int32)
            data["input_mask"] = np.array(input_mask, dtype=np.int32)
            data["segment_ids"] = np.array(segment_ids, dtype=np.int32)
            data["masked_lm_positions"] = np.array(masked_lm_positions, dtype=np.int32)
            data["masked_lm_ids"] = np.array(masked_lm_ids, dtype=np.int32)

            if is_training:
                data["masked_lm_weights"] = np.array(masked_lm_weights, dtype=np.float32)

            n_inputs = len(input_ids)
            if n_inputs < self.batch_size:
                self.batch_size = max(n_inputs, len(self._gpu_ids))

        # convert sample_weight
        if is_training or y:
            sample_weight = self._convert_sample_weight(sample_weight, n_inputs)
            data["sample_weight"] = np.array(sample_weight, dtype=np.float32)

        return data

    def _convert_X(self, X_target, is_training, tokenized):

        # tokenize input texts
        segment_input_tokens = []
        for idx, sample in enumerate(X_target):
            try:
                segment_input_tokens.append(self._convert_x(sample, tokenized))
            except Exception:
                raise ValueError("Wrong input format (line %d): \"%s\". " % (idx, sample))

        input_ids = []
        input_mask = []
        segment_ids = []
        masked_lm_positions = []
        masked_lm_ids = []
        masked_lm_weights = []

        for idx, segments in enumerate(segment_input_tokens):
            _input_tokens = ["[CLS]"]
            _input_ids = []
            _input_mask = [1]
            _segment_ids = [0]
            _masked_lm_positions = []
            _masked_lm_ids = []
            _masked_lm_weights = []

            com.truncate_segments(segments, self.max_seq_length - len(segments) - 1, truncate_method=self.truncate_method)

            for s_id, segment in enumerate(segments):
                _segment_id = min(s_id, 1)
                _input_tokens.extend(segment + ["[SEP]"])
                _input_mask.extend([1] * (len(segment) + 1))
                _segment_ids.extend([_segment_id] * (len(segment) + 1))

            # random sampling of masked tokens
            if is_training:
                if (idx + 1) % 10000 == 0:
                    tf.logging.info("Sampling masks of input %d" % (idx + 1))
                _input_tokens, _masked_lm_positions, _masked_lm_labels = create_masked_lm_predictions(
                    tokens=_input_tokens,
                    masked_lm_prob=self.masked_lm_prob,
                    max_predictions_per_seq=self._max_predictions_per_seq,
                    vocab_words=list(self.tokenizer.vocab.keys()),
                    do_whole_word_mask=self.do_whole_word_mask,
                )
                _masked_lm_ids = self.tokenizer.convert_tokens_to_ids(_masked_lm_labels)
                _masked_lm_weights = [1.0] * len(_masked_lm_positions)

                # padding
                for _ in range(self._max_predictions_per_seq - len(_masked_lm_positions)):
                    _masked_lm_positions.append(0)
                    _masked_lm_ids.append(0)
                    _masked_lm_weights.append(0.0)
            else:
                # `masked_lm_positions` is required for both training
                # and inference of BERT language modeling.
                for i in range(len(_input_tokens)):
                    if _input_tokens[i] == "[MASK]":
                        _masked_lm_positions.append(i)

                # padding
                for _ in range(self._max_predictions_per_seq - len(_masked_lm_positions)):
                    _masked_lm_positions.append(0)
                for _ in range(self._max_predictions_per_seq):
                    _masked_lm_ids.append(0)

            _input_ids = self.tokenizer.convert_tokens_to_ids(_input_tokens)

            # padding
            for _ in range(self.max_seq_length - len(_input_ids)):
                _input_ids.append(0)
                _input_mask.append(0)
                _segment_ids.append(0)

            input_ids.append(_input_ids)
            input_mask.append(_input_mask)
            segment_ids.append(_segment_ids)
            masked_lm_positions.append(_masked_lm_positions)
            masked_lm_ids.append(_masked_lm_ids)
            masked_lm_weights.append(_masked_lm_weights)

        return (input_ids, input_mask, segment_ids, masked_lm_positions, masked_lm_ids, masked_lm_weights)

    def _set_placeholders(self, target, on_export=False, **kwargs):
        self.placeholders = {
            "input_ids": com.get_placeholder(target, "input_ids", [None, self.max_seq_length], tf.int32),
            "input_mask": com.get_placeholder(target, "input_mask", [None, self.max_seq_length], tf.int32),
            "segment_ids": com.get_placeholder(target, "segment_ids", [None, self.max_seq_length], tf.int32),
            "masked_lm_positions": com.get_placeholder(target, "masked_lm_positions", [None, self._max_predictions_per_seq], tf.int32),
            "masked_lm_ids": com.get_placeholder(target, "masked_lm_ids", [None, self._max_predictions_per_seq], tf.int32),
            "masked_lm_weights": com.get_placeholder(target, "masked_lm_weights", [None, self._max_predictions_per_seq], tf.float32),
        }
        if not on_export:
            self.placeholders["sample_weight"] = com.get_placeholder(target, "sample_weight", [None], tf.float32)

    def _forward(self, is_training, split_placeholders, **kwargs):

        model = ELECTRA(
            vocab_size=len(self.tokenizer.vocab),
            model_size=self._model_size,
            is_training=is_training,
            placeholders=split_placeholders,
            sample_weight=split_placeholders.get("sample_weight"),
            max_predictions_per_seq=self._max_predictions_per_seq,
            gen_weight=self.generator_weight,
            disc_weight=self.discriminator_weight,
            **kwargs,
        )

        return model.get_forward_outputs()

    def _get_fit_ops(self, as_feature=False):
        ops = [
            self._tensors["MLM_preds"],
            self._tensors["RTD_preds"],
            self._tensors["RTD_labels"],
            self._tensors["MLM_losses"],
            self._tensors["RTD_losses"],
        ]
        if as_feature:
            ops.extend([
                self.placeholders["input_mask"],
                self.placeholders["masked_lm_positions"],
                self.placeholders["masked_lm_ids"],
            ])
        return ops

    def _get_fit_info(self, output_arrays, feed_dict, as_feature=False):

        if as_feature:
            batch_input_mask = output_arrays[-3]
            batch_mlm_positions = output_arrays[-2]
            batch_mlm_labels = output_arrays[-1]
        else:
            batch_input_mask = feed_dict[self.placeholders["input_mask"]]
            batch_mlm_positions = feed_dict[self.placeholders["masked_lm_positions"]]
            batch_mlm_labels = feed_dict[self.placeholders["masked_lm_ids"]]

        # MLM accuracy
        batch_mlm_preds = output_arrays[0]
        batch_mlm_mask = (batch_mlm_positions > 0)
        mlm_accuracy = np.sum((batch_mlm_preds == batch_mlm_labels) * batch_mlm_mask) / batch_mlm_mask.sum()

        # RTD accuracy
        batch_rtd_preds = output_arrays[1]
        batch_rtd_labels = output_arrays[2]
        rtd_accuracy = np.sum((batch_rtd_preds == batch_rtd_labels) * batch_input_mask) / batch_input_mask.sum()

        # MLM loss
        batch_mlm_losses = output_arrays[3]
        mlm_loss = np.mean(batch_mlm_losses)

        # RTD loss
        batch_rtd_losses = output_arrays[4]
        rtd_loss = np.mean(batch_rtd_losses)

        info = ""
        info += ", MLM accuracy %.4f" % mlm_accuracy
        info += ", RTD accuracy %.4f" % rtd_accuracy
        info += ", MLM loss %.6f" % mlm_loss
        info += ", RTD loss %.6f" % rtd_loss

        return info

    def _get_predict_ops(self):
        return [self._tensors["MLM_preds"], self._tensors["RTD_preds"], self._tensors["RTD_probs"]]

    def _get_predict_outputs(self, batch_outputs):
        n_inputs = len(list(self.data.values())[0])
        output_arrays = list(zip(*batch_outputs))

        # MLM preds
        mlm_preds = []
        mlm_positions = self.data["masked_lm_positions"]
        all_preds = com.transform(output_arrays[0], n_inputs)
        for idx, _preds in enumerate(all_preds):
            _ids = []
            for p_id, _id in enumerate(_preds):
                if mlm_positions[idx][p_id] == 0:
                    break
                _ids.append(_id)
            mlm_preds.append(self.tokenizer.convert_ids_to_tokens(_ids))

        # RTD preds
        rtd_preds = []
        input_ids = self.data["input_ids"]
        input_mask = self.data["input_mask"]
        all_preds = com.transform(output_arrays[1], n_inputs).tolist()
        for idx, _preds in enumerate(all_preds):
            _tokens = []
            _end = sum(input_mask[idx])
            for p_id, _id in enumerate(_preds[:_end]):
                if _id == 0:
                    _tokens.append(self.tokenizer.convert_ids_to_tokens([input_ids[idx][p_id]])[0])
                else:
                    _tokens.append("[REPLACED]")
            rtd_preds.append(_tokens)

        # RTD probs
        rtd_probs = com.transform(output_arrays[2], n_inputs)

        outputs = {}
        outputs["mlm_preds"] = mlm_preds
        outputs["rtd_preds"] = rtd_preds
        outputs["rtd_probs"] = rtd_probs

        return outputs
