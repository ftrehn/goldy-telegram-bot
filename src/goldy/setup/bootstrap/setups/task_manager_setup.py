import logging
from typing import Final

from taskiq import AsyncBroker, ScheduleSource, async_shared_broker
from taskiq.middlewares import SmartRetryMiddleware
from taskiq_aio_pika import AioPikaBroker, Exchange, Queue
from taskiq_redis import ListRedisScheduleSource, RedisAsyncResultBackend

from goldy.setup.configs.rabbitmq_config import RabbitMQConfig
from goldy.setup.configs.redis_config import RedisConfig
from goldy.setup.configs.taskiq_config import TaskIQConfig

logger: Final[logging.Logger] = logging.getLogger(__name__)


def setup_task_manager(
    taskiq_config: TaskIQConfig,
    rabbitmq_config: RabbitMQConfig,
    redis_config: RedisConfig,
) -> AsyncBroker:
    """Creates the taskiq RabbitMQ broker with a Redis result backend.

    The queue is bound by an explicit routing key rather than left to default,
    so a second consumer added later gets its own binding instead of quietly
    stealing messages from this one.

    A dead-letter queue is declared up front because the alternative is worse
    than it sounds: without one, a message RabbitMQ gives up on is discarded,
    and the first sign of trouble is work that never happened and left no trace.

    Results live in Redis rather than RabbitMQ because they are read by task
    status polling, which wants cheap key lookups with a TTL — a queue is a poor
    place to look something up by id.
    """
    logger.debug("Creating taskiq broker...")

    broker: AsyncBroker = AioPikaBroker(
        url=rabbitmq_config.uri,
        qos=taskiq_config.qos,
        exchange=Exchange(name=taskiq_config.exchange_name),
        task_queues=[
            Queue(
                name=taskiq_config.queue_name,
                routing_key=taskiq_config.routing_key,
            ),
        ],
        dead_letter_queue=Queue(name=taskiq_config.dead_letter_queue_name),
    ).with_result_backend(
        RedisAsyncResultBackend(
            redis_url=redis_config.worker_uri,
            result_ex_time=taskiq_config.result_ex_time,
        ),
    )

    async_shared_broker.default_broker(broker)
    logger.debug("Taskiq broker created and set as default")
    return broker


def setup_task_manager_middlewares(
    broker: AsyncBroker,
    taskiq_config: TaskIQConfig,
) -> AsyncBroker:
    """Applies the retry policy to the broker.

    Jitter matters here specifically because replicas fail together — a broker
    blip hits every worker at once, and without jitter they would all retry in
    the same instant and reproduce the outage.
    """
    return broker.with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=taskiq_config.default_retry_count,
            default_delay=taskiq_config.default_delay,
            use_jitter=taskiq_config.use_jitter,
            use_delay_exponent=taskiq_config.use_delay_exponent,
            max_delay_exponent=taskiq_config.max_delay_exponent,
        ),
    )


def setup_schedule_source(redis_config: RedisConfig) -> ScheduleSource:
    """Creates the store the scheduler reads pending schedules from.

    Its own Redis database, separate from results: schedules outlive the tasks
    they spawn, and putting them beside short-lived results means a cleanup of
    one can take the other with it.

    The list-backed source rather than the plain one: the latter is deprecated,
    and it scanned keys to find due schedules, which degrades as they pile up.
    """
    return ListRedisScheduleSource(url=redis_config.schedule_source_uri)
