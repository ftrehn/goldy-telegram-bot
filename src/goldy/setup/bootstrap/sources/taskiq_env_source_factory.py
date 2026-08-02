from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.taskiq_config import TaskIQConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class TaskIQEnvSourceFactory(SourceFactory):
    """Maps ``TASKIQ_*`` environment variables onto :class:`TaskIQConfig`."""

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[TaskIQConfig].exchange_name: "TASKIQ_EXCHANGE_NAME",
                F[TaskIQConfig].queue_name: "TASKIQ_QUEUE_NAME",
                F[TaskIQConfig].routing_key: "TASKIQ_ROUTING_KEY",
                F[TaskIQConfig].dead_letter_queue_name: "TASKIQ_DEAD_LETTER_QUEUE_NAME",
                F[TaskIQConfig].qos: "TASKIQ_QOS",
                F[TaskIQConfig].result_ex_time: "TASKIQ_RESULT_EX_TIME",
                F[TaskIQConfig].default_retry_count: "TASKIQ_DEFAULT_RETRY_COUNT",
                F[TaskIQConfig].default_delay: "TASKIQ_DEFAULT_DELAY",
                F[TaskIQConfig].use_jitter: "TASKIQ_USE_JITTER",
                F[TaskIQConfig].use_delay_exponent: "TASKIQ_USE_DELAY_EXPONENT",
                F[TaskIQConfig].max_delay_exponent: "TASKIQ_MAX_DELAY_EXPONENT",
            },
        )
