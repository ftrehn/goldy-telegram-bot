import logging
from typing import Final

from faststream.rabbit import RabbitBroker
from taskiq import AsyncBroker, ScheduleSource, TaskiqScheduler, async_shared_broker
from taskiq.middlewares import SmartRetryMiddleware
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_aio_pika import AioPikaBroker, Exchange, Queue
from taskiq_redis import ListRedisScheduleSource, RedisAsyncResultBackend

from goldy.infrastructure.task_manager.tasks import setup_outbox_tasks
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


def setup_event_broker(rabbitmq_config: RabbitMQConfig) -> RabbitBroker:
    """FastStream's connection to the domain event exchange.

    Separate from taskiq's: taskiq owns a work queue whose messages are
    consumed competitively, while domain events go to a topic exchange that any
    number of consumers can bind to independently.

    Both a publisher and a consumer since the notifier was built. The relay
    publishes to the exchange on its cron tick and the notification subscribers
    bind to it, which is why the worker *starts* this broker rather than only
    connecting it — connecting opens the channel, starting is what makes a
    registered subscriber actually consume.

    Still created here and handed to the container rather than given a
    FastStream app and a lifespan of its own: the worker process already has
    one lifecycle, taskiq's, and a second one would give the two different
    ideas about when shutdown happened.
    """
    return RabbitBroker(url=rabbitmq_config.uri)


def setup_task_manager_tasks(broker: AsyncBroker) -> None:
    """Registers every background task on the broker.

    Registration is what makes a task name resolvable, and the name is all the
    scheduler has to go on. A task missing from here does not fail at startup —
    it fails as work that never happened, which is the hardest kind of failure
    to notice, so every entry point calls this and so do the tests.
    """
    setup_outbox_tasks(broker)


def setup_scheduler(
    broker: AsyncBroker,
    schedule_source: ScheduleSource,
) -> TaskiqScheduler:
    """Builds the scheduler that fires the cron tasks.

    Takes the worker's own broker rather than building one: a separately built
    broker could drift in queue naming and then silently fire into a queue
    nobody consumes. The scheduler only enqueues — the worker still does the
    work.

    Two sources, because schedules arrive two ways. ``LabelScheduleSource``
    reads the cron declared at registration, which is what drives the outbox
    relay; the Redis source holds schedules created at runtime and survives a
    restart. With only the latter, a cron declared on a task would never fire.
    """
    return TaskiqScheduler(
        broker=broker,
        sources=[LabelScheduleSource(broker), schedule_source],
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
