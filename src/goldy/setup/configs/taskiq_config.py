from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TaskIQConfig:
    """Behaviour of the taskiq broker, independent of where it connects.

    Split from :class:`RabbitMQConfig` and :class:`RedisConfig` on purpose:
    those say *where* the broker talks, this says *how* it behaves. Retry policy
    and queue naming change far more often than connection details, and they
    change per environment rather than per deployment target.

    Attributes:
        exchange_name: Exchange tasks are published to.
        queue_name: Queue workers consume from.
        routing_key: Key the queue is bound to the exchange with.
        dead_letter_queue_name: Where a message goes once RabbitMQ gives up on
            it, so a poisoned task can be inspected instead of vanishing.
        qos: How many messages one worker prefetches. Low on purpose: a large
            prefetch lets one replica hoard the queue while another idles.
        result_ex_time: Seconds a task result is kept in Redis.
        default_retry_count: Attempts before a failing task is given up on.
        default_delay: Seconds before the first retry.
        use_jitter: Whether to spread retries randomly, so replicas that failed
            together do not retry in lockstep.
        use_delay_exponent: Whether the delay grows exponentially per attempt.
        max_delay_exponent: Ceiling on the exponential delay, in seconds.
    """

    exchange_name: str = "goldy"
    queue_name: str = "goldy.tasks"
    routing_key: str = "goldy.tasks"
    dead_letter_queue_name: str = "goldy.dead_letter"
    qos: int = 10
    result_ex_time: int = 1000
    default_retry_count: int = 3
    default_delay: float = 5.0
    use_jitter: bool = True
    use_delay_exponent: bool = True
    max_delay_exponent: float = 60.0
