import numpy as np

from .fastbert import FastBERTClsDistillor, convert_ignore_cls
from .._base_._base_classifier import ClassifierModule
from ..bert.bert_classifier import BERTClassifier
from ..bert.bert import BERTConfig
from ...token import WordPieceTokenizer
from ...third import tf
from ... import com


class FastBERTClassifier(BERTClassifier, ClassifierModule):
    """ Single-label classifier on FastBERT, a distillation model. """

    def __init__(
        self,
        config_file,
        vocab_file,
        max_seq_length=128,
        label_size=None,
        init_checkpoint=None,
        output_dir=None,
        gpu_ids=None,
        drop_pooler=False,
        cls_model="self-attention",
        do_lower_case=True,
        truncate_method="LIFO",
    ):
        self.__init_args__ = locals()
        super(ClassifierModule, self).__init__(init_checkpoint, output_dir, gpu_ids)

        self.max_seq_length = max_seq_length
        self.label_size = label_size
        self.truncate_method = truncate_method
        self._cls_model = cls_model
        self._ignore_cls = [0]
        self._speed = 0.1
        self._drop_pooler = drop_pooler

        self.bert_config = BERTConfig.from_json_file(config_file)
        self.tokenizer = WordPieceTokenizer(vocab_file, do_lower_case)
        self.decay_power = "unsupported"

        assert label_size, ("`label_size` can't be None.")
        if "[CLS]" not in self.tokenizer.vocab:
            self.tokenizer.add("[CLS]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[CLS]` into vocabulary.")
        if "[SEP]" not in self.tokenizer.vocab:
            self.tokenizer.add("[SEP]")
            self.bert_config.vocab_size += 1
            tf.logging.info("Add necessary token `[SEP]` into vocabulary.")

    def predict(self, X=None, X_tokenized=None, batch_size=8, speed=0.1, ignore_cls="0"):
        """ Inference on the model.

        Args:
            X: list. A list object consisting untokenized inputs.
            X_tokenized: list. A list object consisting tokenized inputs.
              Either `X` or `X_tokenized` should be None.
            batch_size: int. The size of batch in each step.
            speed: float. Threshold for leaving model in advance, which
              should be within [0, 1].
            ignore_cls: list. A list object of integers that stands for
              the classifiers to ignore. The more classifier ignored, the
              faster inference is.
        Returns:
            A dict object of model outputs.
        """
        ignore_cls = convert_ignore_cls(ignore_cls)

        if ignore_cls != self._ignore_cls:
            self._ignore_cls = ignore_cls
            self._session_mode = None

        if speed != self._speed:
            self._speed = speed
            self._session_mode = None

        return super(ClassifierModule, self).predict(X, X_tokenized, batch_size)

    def score(self, X=None, y=None, sample_weight=None, X_tokenized=None, batch_size=8, speed=0.1, ignore_cls="0"):
        """ Inference on the model with scoring.

        Args:
            X: list. A list object consisting untokenized inputs.
            y: list. A list object consisting labels.
            sample_weight: list. A list object of float-convertable values.
            X_tokenized: list. A list object consisting tokenized inputs.
              Either `X` or `X_tokenized` should be None.
            batch_size: int. The size of batch in each step.
            speed: float. Threshold for leaving model in advance, which
              should be within [0, 1].
            ignore_cls: list. A list object of integers that stands for
              the classifiers to ignore. The more classifier ignored, the
              faster inference is.
        Returns:
            A dict object of output metrics.
        """
        ignore_cls = convert_ignore_cls(ignore_cls)

        if ignore_cls != self._ignore_cls:
            self._ignore_cls = ignore_cls
            self._session_mode = None

        if speed != self._speed:
            self._speed = speed
            self._session_mode = None

        return super(ClassifierModule, self).score(
            X, y, sample_weight, X_tokenized, batch_size)

    def export(self, export_dir, speed=0.1, ignore_cls="0", rename_inputs=None, rename_outputs=None, ignore_outputs=None):
        """ Export model into SavedModel files.

        Args:
            export_dir: str. Directory to which the model is saved.
            speed: float. Threshold for leaving model in advance, which
              should be within [0, 1].
            ignore_cls: list. A list object of integers that stands for
              the classifiers to ignore. The more classifier ignored, the
              faster inference is.
            rename_inputs: dict. Mapping of original name to target name.
            rename_outputs: dict. Mapping of original name to target name.
            ignore_outputs: list. Name of outputs to ignore.
        Returns:
            None
        """
        ignore_cls = convert_ignore_cls(ignore_cls)

        if ignore_cls != self._ignore_cls:
            self._ignore_cls = ignore_cls
            self._session_mode = None

        if speed != self._speed:
            self._speed = speed
            self._session_mode = None

        return super(ClassifierModule, self).export(export_dir, rename_inputs, rename_outputs, ignore_outputs)

    def convert(self, X=None, y=None, sample_weight=None, X_tokenized=None, is_training=False, is_parallel=False):
        self._assert_legal(X, y, sample_weight, X_tokenized)

        if is_training:
            assert y is None, "Training of %s is unsupervised. `y` should be None." % self.__class__.__name__

        n_inputs = None
        data = {}

        # convert X
        if X is not None or X_tokenized is not None:
            tokenized = False if X is not None else X_tokenized
            input_ids, input_mask, segment_ids = self._convert_X(X_tokenized if tokenized else X, tokenized=tokenized)
            data["input_ids"] = np.array(input_ids, dtype=np.int32)
            data["input_mask"] = np.array(input_mask, dtype=np.int32)
            data["segment_ids"] = np.array(segment_ids, dtype=np.int32)
            n_inputs = len(input_ids)

            if n_inputs < self.batch_size:
                self.batch_size = max(n_inputs, len(self._gpu_ids))

        if y is not None:
            # convert y and sample_weight
            label_ids = self._convert_y(y)
            data["label_ids"] = np.array(label_ids, dtype=np.int32)

        # convert sample_weight
        if is_training or y is not None:
            sample_weight = self._convert_sample_weight(sample_weight, n_inputs)
            data["sample_weight"] = np.array(sample_weight, dtype=np.float32)

        return data

    def _forward(self, is_training, placeholders, **kwargs):

        model = FastBERTClsDistillor(
            bert_config=self.bert_config,
            is_training=is_training,
            input_ids=placeholders["input_ids"],
            input_mask=placeholders["input_mask"],
            segment_ids=placeholders["segment_ids"],
            sample_weight=placeholders.get("sample_weight"),
            drop_pooler=self._drop_pooler,
            speed=self._speed,
            ignore_cls=[] if is_training else self._ignore_cls,
            cls_model=self._cls_model,
            label_size=self.label_size,
            **kwargs,
        )
        train_loss, tensors = model.get_forward_outputs()
        return train_loss, tensors

    def _get_fit_ops(self, from_tfrecords=False):
        return [self.tensors["losses"]]

    def _get_fit_info(self, output_arrays, feed_dict, from_tfrecords=False):

        # loss
        batch_losses = output_arrays[0]
        loss = np.mean(batch_losses)

        info = ""
        info += ", distill loss %.6f" % loss

        return info

    def _get_predict_ops(self):
        return [self.tensors["probs"]]

    def _get_predict_outputs(self, output_arrays, n_inputs):

        def _uncertainty(prob):
            if prob < 1e-20 or 1 - prob < 1e-20:
                prob = 1e-20
            return (prob * np.log(prob) + (1 - prob) * np.log(1 - prob)) / np.log(1 / self.label_size)

        def _permutate(batch_probs):
            n_device = max(len(self._gpu_ids), 1)
            d_batch_size = self.batch_size // n_device
            probs = np.zeros((self.batch_size, self.label_size))
            sources = np.zeros((self.batch_size), dtype=np.int32)
            max_loop = self.bert_config.num_hidden_layers + 1 - len(self._ignore_cls)
            keep_cls = [
                cls_idx for cls_idx in list(range(self.bert_config.num_hidden_layers + 1))
                if cls_idx not in self._ignore_cls
            ]
            i = 0

            for d in range(n_device):
                unfinished = [k + i for k in range(d_batch_size)]

                for loop in range(max_loop):
                    source = keep_cls[loop]
                    next_unfinished = []

                    for k in range(len(unfinished)):
                        if _uncertainty(batch_probs[i][0]) < self._speed or loop == max_loop - 1:
                            probs[unfinished[k]] = batch_probs[i]
                            sources[unfinished[k]] = source
                        else:
                            next_unfinished.append(unfinished[k])
                        i += 1
                    unfinished = next_unfinished
            assert i == len(batch_probs)
            return probs, sources

        # probs
        probs_arrays = []
        sources_arrays = []
        for batch_probs in output_arrays[0]:
            probs_array, sources_array = _permutate(batch_probs)
            probs_arrays.append(probs_array)
            sources_arrays.append(sources_array)
        probs = com.transform(probs_arrays, n_inputs)
        sources = com.transform(sources_arrays, n_inputs).tolist()

        # preds
        preds = np.argmax(probs, axis=-1).tolist()
        if self._id_to_label:
            preds = [self._id_to_label[idx] if idx < len(self._id_to_label) else None for idx in preds]

        outputs = {}
        outputs["preds"] = preds
        outputs["probs"] = probs
        outputs["sources"] = sources

        return outputs

    def _get_score_ops(self):
        return [self.tensors["probs"]]

    def _get_score_outputs(self, output_arrays, n_inputs):

        def _uncertainty(prob):
            if prob < 1e-20 or 1 - prob < 1e-20:
                prob = 1e-20
            return (prob * np.log(prob) + (1 - prob) * np.log(1 - prob)) / np.log(1 / self.label_size)

        def _permutate(batch_probs):
            n_device = max(len(self._gpu_ids), 1)
            d_batch_size = self.batch_size // n_device
            probs = np.zeros((self.batch_size, self.label_size))
            sources = np.zeros((self.batch_size), dtype=np.int32)
            max_loop = self.bert_config.num_hidden_layers + 1 - len(self._ignore_cls)
            keep_cls = [
                cls_idx for cls_idx in list(range(self.bert_config.num_hidden_layers + 1))
                if cls_idx not in self._ignore_cls
            ]
            i = 0

            for d in range(n_device):
                unfinished = [k + i for k in range(d_batch_size)]

                for loop in range(max_loop):
                    source = keep_cls[loop]
                    next_unfinished = []

                    for k in range(len(unfinished)):
                        if _uncertainty(batch_probs[i][0]) < self._speed or loop == max_loop - 1:
                            probs[unfinished[k]] = batch_probs[i]
                            sources[unfinished[k]] = source
                        else:
                            next_unfinished.append(unfinished[k])
                        i += 1
                    unfinished = next_unfinished
            assert i == len(batch_probs)
            return probs, sources

        def _transform(output_arrays):
            if len(output_arrays[0].shape) > 1:
                return np.vstack(output_arrays)[:n_inputs]
            return np.hstack(output_arrays)[:n_inputs]

        # accuracy
        probs_arrays = []
        for batch_probs in output_arrays[0]:
            probs_array, _ = _permutate(batch_probs)
            probs_arrays.append(probs_array)
        probs = _transform(probs_arrays)
        preds = np.argmax(probs, axis=-1)
        labels = self.data["label_ids"]
        accuracy = np.mean(preds == labels)

        # loss
        losses = [-np.log(probs[i][label]) for i, label in enumerate(labels)]
        sample_weight = self.data["sample_weight"]
        losses = np.array(losses) * sample_weight
        loss = np.mean(losses)

        outputs = {}
        outputs["accuracy"] = accuracy
        outputs["loss"] = loss

        return outputs
