"""Valid environment payloads, one per config, with every key overridable.

A test that varies one variable states only that variable, so what it is
actually checking is not buried in ten lines of scaffolding.
"""


def postgres_env(**overrides: str) -> dict[str, str]:
    """Valid ``POSTGRES_*`` values; override any key."""
    return {
        "POSTGRES_USER": "app",
        "POSTGRES_PASSWORD": "s3cr3t",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "goldy",
        "POSTGRES_DRIVER": "asyncpg",
    } | overrides


def sqlalchemy_env(**overrides: str) -> dict[str, str]:
    """Valid ``DB_*`` values; override any key.

    Only the required fields are provided — the optional ones fall back to
    their dataclass defaults, which is worth exercising.
    """
    return {
        "DB_POOL_PRE_PING": "true",
        "DB_POOL_RECYCLE": "30",
        "DB_POOL_SIZE": "10",
        "DB_POOL_MAX_OVERFLOW": "5",
        "DB_ECHO": "false",
    } | overrides


def redis_env(**overrides: str) -> dict[str, str]:
    """Valid ``REDIS_*`` values; override any key."""
    return {
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "REDIS_USER": "",
        "REDIS_PASSWORD": "",
        "REDIS_WORKER_DB": "1",
        "REDIS_SCHEDULE_SOURCE_DB": "2",
        "REDIS_CACHE_DB": "0",
        "REDIS_FSM_DB": "3",
    } | overrides


def rabbitmq_env(**overrides: str) -> dict[str, str]:
    """Valid ``RABBITMQ_*`` values; override any key."""
    return {
        "RABBITMQ_HOST": "localhost",
        "RABBITMQ_PORT": "5672",
        "RABBITMQ_USER": "guest",
        "RABBITMQ_PASSWORD": "guest",
        "RABBITMQ_VHOST": "/",
    } | overrides


def telegram_env(**overrides: str) -> dict[str, str]:
    """Valid ``TELEGRAM_*`` values; override any key."""
    return {
        "TELEGRAM_BOT_TOKEN": "123456789:AAFakeTokenForTestsOnly",
        "TELEGRAM_USE_REDIS_STORAGE": "true",
        "TELEGRAM_USE_REDIS_EVENT_ISOLATION": "true",
        "TELEGRAM_USE_I18N_ISOLATION": "true",
        "TELEGRAM_DEFAULT_LOCALE": "ru",
        "TELEGRAM_DROP_PENDING_UPDATES": "true",
    } | overrides


def admin_env(**overrides: str) -> dict[str, str]:
    """Valid ``GOLDY_ADMIN_*`` values; override any key."""
    return {"GOLDY_ADMIN_PHONE_NUMBERS": ""} | overrides


def catalog_env(**overrides: str) -> dict[str, str]:
    """Valid ``GOLDY_DEFAULT_PRICE_TYPE_ID`` value; override it to break it."""
    return {"GOLDY_DEFAULT_PRICE_TYPE_ID": "1c-price-type-wholesale"} | overrides


def taskiq_env(**overrides: str) -> dict[str, str]:
    """Valid ``TASKIQ_*`` values; override any key."""
    return {
        "TASKIQ_EXCHANGE_NAME": "goldy",
        "TASKIQ_QUEUE_NAME": "goldy.tasks",
        "TASKIQ_ROUTING_KEY": "goldy.tasks",
        "TASKIQ_DEAD_LETTER_QUEUE_NAME": "goldy.dead_letter",
        "TASKIQ_QOS": "10",
        "TASKIQ_RESULT_EX_TIME": "1000",
        "TASKIQ_DEFAULT_RETRY_COUNT": "3",
        "TASKIQ_DEFAULT_DELAY": "5.0",
        "TASKIQ_USE_JITTER": "true",
        "TASKIQ_USE_DELAY_EXPONENT": "true",
        "TASKIQ_MAX_DELAY_EXPONENT": "60.0",
    } | overrides
