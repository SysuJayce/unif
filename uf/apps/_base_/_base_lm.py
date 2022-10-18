from ...core import BaseModule


class LMModule(BaseModule):
    """ Application class of language modeling (LM). """

    def fit_from_tfrecords(
        self,
        batch_size=32,
        learning_rate=5e-5,
        target_steps=None,
        total_steps=1000000,
        warmup_ratio=0.01,        # 默认值不同
        print_per_secs=0.1,
        save_per_steps=10000,
        tfrecords_files=None,
        n_jobs=None,
        **kwargs,
    ):
        super().fit_from_tfrecords(
            batch_size,
            learning_rate,
            target_steps,
            total_steps,
            warmup_ratio,
            print_per_secs,
            save_per_steps,
            tfrecords_files,
            n_jobs,
            **kwargs,
        )
    fit_from_tfrecords.__doc__ = BaseModule.fit_from_tfrecords.__doc__

    def fit(
        self,
        X=None, y=None, sample_weight=None, X_tokenized=None,
        batch_size=32,
        learning_rate=5e-5,
        target_steps=None,
        total_steps=1000000,
        warmup_ratio=0.01,        # 默认值不同
        print_per_secs=0.1,
        save_per_steps=10000,
        **kwargs,
    ):
        super().fit(
            X, y, sample_weight, X_tokenized,
            batch_size,
            learning_rate,
            target_steps,
            total_steps,
            warmup_ratio,
            print_per_secs,
            save_per_steps,
            **kwargs,
        )
    fit.__doc__ = BaseModule.fit.__doc__

    def score(self, *args, **kwargs):
        raise AttributeError("`score` method is not supported for unsupervised language modeling (LM) modules.")