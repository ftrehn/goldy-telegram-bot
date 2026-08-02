from typing import TYPE_CHECKING, Final, override

from dature import V, load

from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.configs.taskiq_config import TaskIQConfig

from .consts import DELAY_MIN, MAX_DELAY_EXPONENT_MIN, QOS_MIN, RETRY_COUNT_MIN

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


class TaskIQConfigLoader(ConfigLoader[TaskIQConfig]):
    """``dature``-backed loader for :class:`TaskIQConfig`."""

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> TaskIQConfig:
        return load(
            self._source_factory.create(),
            schema=TaskIQConfig,
            root_validators=self._root_validators(),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        return (
            V.root(
                lambda c: c.default_retry_count >= RETRY_COUNT_MIN,
                error_message=(
                    f"TASKIQ_DEFAULT_RETRY_COUNT must be at least {RETRY_COUNT_MIN}"
                ),
            ),
            V.root(
                lambda c: c.default_delay >= DELAY_MIN,
                error_message=f"TASKIQ_DEFAULT_DELAY must be at least {DELAY_MIN}",
            ),
            V.root(
                lambda c: c.max_delay_exponent >= MAX_DELAY_EXPONENT_MIN,
                error_message=(
                    f"TASKIQ_MAX_DELAY_EXPONENT must be at least {MAX_DELAY_EXPONENT_MIN}"
                ),
            ),
            V.root(
                lambda c: c.result_ex_time > 0,
                error_message="TASKIQ_RESULT_EX_TIME must be positive",
            ),
            V.root(
                lambda c: c.qos >= QOS_MIN,
                error_message=(
                    f"TASKIQ_QOS must be at least {QOS_MIN} — a prefetch of zero "
                    f"stops the worker consuming anything at all"
                ),
            ),
            # Sharing a name would bind the dead-letter queue to the same
            # routing key as the live one, so a poisoned message would be
            # redelivered to the workers that already rejected it.
            V.root(
                lambda c: c.queue_name != c.dead_letter_queue_name,
                error_message=(
                    "TASKIQ_QUEUE_NAME and TASKIQ_DEAD_LETTER_QUEUE_NAME must differ"
                ),
            ),
        )
