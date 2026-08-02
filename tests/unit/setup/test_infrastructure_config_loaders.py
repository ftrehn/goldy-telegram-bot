"""The loaders for the infrastructure configs.

A config that loads wrong fails at startup with a confusing message, or worse,
starts and points the service at the wrong place. These check the validation
rules and the derived connection strings — the parts that are ours rather than
dature's.
"""

import pytest
from dature.errors.exceptions import DatureConfigError

from goldy.setup.bootstrap.loaders.admin_config_loader import AdminConfigLoader
from goldy.setup.bootstrap.loaders.alchemy_config_loader import SQLAlchemyConfigLoader
from goldy.setup.bootstrap.loaders.postgres_config_loader import PostgresConfigLoader
from goldy.setup.bootstrap.loaders.rabbitmq_config_loader import RabbitMQConfigLoader
from goldy.setup.bootstrap.loaders.redis_config_loader import RedisConfigLoader
from goldy.setup.bootstrap.loaders.taskiq_config_loader import TaskIQConfigLoader
from goldy.setup.bootstrap.loaders.telegram_config_loader import TelegramConfigLoader
from tests.unit.factories.source_stubs import (
    admin_source_stub,
    postgres_source_stub,
    rabbitmq_source_stub,
    redis_source_stub,
    sqlalchemy_source_stub,
    taskiq_source_stub,
    telegram_source_stub,
)
from tests.unit.support import render_exception


def test_postgres_builds_the_uri_from_its_parts() -> None:
    config = PostgresConfigLoader(postgres_source_stub()).load()

    assert config.uri == "postgresql+asyncpg://app:s3cr3t@localhost:5432/goldy"


@pytest.mark.parametrize("port", ("0", "65536", "-1"))
def test_postgres_rejects_a_port_outside_the_valid_range(port: str) -> None:
    loader = PostgresConfigLoader(postgres_source_stub(POSTGRES_PORT=port))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "POSTGRES_PORT must be between 1 and 65535" in render_exception(excinfo.value)


def test_postgres_password_is_masked_in_error_output() -> None:
    """A startup failure is a log, and the password must never reach one."""
    stub = postgres_source_stub(
        POSTGRES_PASSWORD="TOP-SECRET-VALUE",
        POSTGRES_PORT="999999",
    )

    loader = PostgresConfigLoader(stub)

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "TOP-SECRET-VALUE" not in render_exception(excinfo.value)


def test_redis_gives_each_purpose_its_own_database() -> None:
    """A cache flush must not take the dialogue state with it."""
    config = RedisConfigLoader(redis_source_stub()).load()

    assert config.worker_uri == "redis://localhost:6379/1"
    assert config.schedule_source_uri == "redis://localhost:6379/2"
    assert config.cache_uri == "redis://localhost:6379/0"
    assert config.fsm_uri == "redis://localhost:6379/3"


def test_redis_rejects_two_purposes_sharing_a_database() -> None:
    """Silently sharing a database is the failure this catches at startup."""
    stub = redis_source_stub(REDIS_WORKER_DB="1", REDIS_SCHEDULE_SOURCE_DB="1")

    loader = RedisConfigLoader(stub)

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "different database indexes" in render_exception(excinfo.value)


def test_redis_rejects_a_user_without_a_password() -> None:
    loader = RedisConfigLoader(redis_source_stub(REDIS_USER="app"))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "REDIS_USER requires REDIS_PASSWORD" in render_exception(excinfo.value)


def test_rabbitmq_encodes_the_default_virtual_host() -> None:
    """A bare ``/`` would read as an empty name and connect somewhere else."""
    config = RabbitMQConfigLoader(rabbitmq_source_stub()).load()

    assert config.uri == "amqp://guest:guest@localhost:5672/%2F"


def test_rabbitmq_names_a_custom_virtual_host_verbatim() -> None:
    config = RabbitMQConfigLoader(rabbitmq_source_stub(RABBITMQ_VHOST="goldy")).load()

    assert config.uri == "amqp://guest:guest@localhost:5672/goldy"


def test_rabbitmq_escapes_credentials_that_would_corrupt_the_uri() -> None:
    """A password containing ``@`` or ``/`` would otherwise split the URI."""
    stub = rabbitmq_source_stub(RABBITMQ_USER="a/b", RABBITMQ_PASSWORD="p@ss/word")

    config = RabbitMQConfigLoader(stub).load()

    assert config.uri == "amqp://a%2Fb:p%40ss%2Fword@localhost:5672/%2F"


@pytest.mark.parametrize("port", ("0", "65536"))
def test_rabbitmq_rejects_a_port_outside_the_valid_range(port: str) -> None:
    loader = RabbitMQConfigLoader(rabbitmq_source_stub(RABBITMQ_PORT=port))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "RABBITMQ_PORT must be between 1 and 65535" in render_exception(excinfo.value)


@pytest.mark.parametrize(
    ("variable", "value", "expected"),
    (
        ("RABBITMQ_HOST", "   ", "RABBITMQ_HOST must not be empty"),
        ("RABBITMQ_USER", "", "RABBITMQ_USER must not be empty"),
        ("RABBITMQ_VHOST", "", "RABBITMQ_VHOST must not be empty"),
    ),
)
def test_rabbitmq_rejects_blank_connection_parts(
    variable: str,
    value: str,
    expected: str,
) -> None:
    loader = RabbitMQConfigLoader(rabbitmq_source_stub(**{variable: value}))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert expected in render_exception(excinfo.value)


def test_rabbitmq_password_is_masked_in_error_output() -> None:
    stub = rabbitmq_source_stub(
        RABBITMQ_PASSWORD="TOP-SECRET-VALUE",
        RABBITMQ_PORT="999999",
    )

    loader = RabbitMQConfigLoader(stub)

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "TOP-SECRET-VALUE" not in render_exception(excinfo.value)


def test_taskiq_loads_its_queue_names_and_retry_policy() -> None:
    config = TaskIQConfigLoader(taskiq_source_stub()).load()

    assert config.exchange_name == "goldy"
    assert config.queue_name == "goldy.tasks"
    assert config.dead_letter_queue_name == "goldy.dead_letter"
    assert config.default_retry_count == 3
    assert config.use_jitter
    assert config.use_delay_exponent


@pytest.mark.parametrize(
    ("variable", "value"),
    (
        ("TASKIQ_DEFAULT_RETRY_COUNT", "-1"),
        ("TASKIQ_DEFAULT_DELAY", "-1"),
        ("TASKIQ_MAX_DELAY_EXPONENT", "0"),
        ("TASKIQ_RESULT_EX_TIME", "0"),
        ("TASKIQ_QOS", "0"),
    ),
)
def test_taskiq_rejects_a_nonsensical_policy(variable: str, value: str) -> None:
    loader = TaskIQConfigLoader(taskiq_source_stub(**{variable: value}))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert variable in render_exception(excinfo.value)


def test_taskiq_rejects_a_dead_letter_queue_sharing_the_live_name() -> None:
    """Sharing the name feeds poisoned messages back to the workers that rejected them."""
    stub = taskiq_source_stub(
        TASKIQ_QUEUE_NAME="goldy.tasks",
        TASKIQ_DEAD_LETTER_QUEUE_NAME="goldy.tasks",
    )

    loader = TaskIQConfigLoader(stub)

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "must differ" in render_exception(excinfo.value)


def test_redis_rejects_the_fsm_database_colliding_with_the_cache() -> None:
    """Sharing with the cache means a routine flush drops everyone mid-dialogue."""
    loader = RedisConfigLoader(redis_source_stub(REDIS_FSM_DB="0"))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "four different database indexes" in render_exception(excinfo.value)


def test_telegram_loads_its_storage_flags() -> None:
    config = TelegramConfigLoader(telegram_source_stub()).load()

    assert config.use_redis_storage is True
    assert config.use_redis_event_isolation is True
    assert config.default_locale == "ru"


@pytest.mark.parametrize("token", ("", "   ", "no-colon-here"))
def test_telegram_rejects_a_token_that_is_not_shaped_like_one(token: str) -> None:
    """Turns the commonest deployment mistake into a startup error, not a 401."""
    loader = TelegramConfigLoader(telegram_source_stub(TELEGRAM_BOT_TOKEN=token))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "TELEGRAM_BOT_TOKEN" in render_exception(excinfo.value)


def test_telegram_bot_token_is_masked_in_error_output() -> None:
    """A startup failure is a log, and the token is a credential."""
    stub = telegram_source_stub(
        TELEGRAM_BOT_TOKEN="123:TOP-SECRET-VALUE",
        TELEGRAM_DEFAULT_LOCALE="de",
    )

    loader = TelegramConfigLoader(stub)

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "TOP-SECRET-VALUE" not in render_exception(excinfo.value)


def test_telegram_rejects_a_default_locale_we_do_not_ship() -> None:
    loader = TelegramConfigLoader(telegram_source_stub(TELEGRAM_DEFAULT_LOCALE="de"))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "TELEGRAM_DEFAULT_LOCALE" in render_exception(excinfo.value)


def test_no_configured_admins_is_a_valid_configuration() -> None:
    """A fresh deployment has none, and that must not stop the bot booting."""
    config = AdminConfigLoader(admin_source_stub()).load()

    assert not config.phone_numbers


def test_admin_numbers_are_rejected_when_one_of_them_is_nonsense() -> None:
    """A typo here means an administrator silently never gets their role."""
    stub = admin_source_stub(GOLDY_ADMIN_PHONE_NUMBERS="+79991234567,not-a-number")

    loader = AdminConfigLoader(stub)

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert "GOLDY_ADMIN_PHONE_NUMBERS" in render_exception(excinfo.value)


def test_sqlalchemy_optional_fields_fall_back_to_their_defaults() -> None:
    """The stub sets only the required keys, so this proves the defaults apply."""
    config = SQLAlchemyConfigLoader(sqlalchemy_source_stub()).load()

    assert config.pool_size == 10
    assert config.max_overflow == 5
    assert config.echo is False


@pytest.mark.parametrize(
    ("variable", "value"),
    (
        ("DB_POOL_SIZE", "0"),
        ("DB_POOL_SIZE", "1001"),
        ("DB_POOL_RECYCLE", "0"),
        ("DB_POOL_MAX_OVERFLOW", "-1"),
    ),
)
def test_sqlalchemy_rejects_a_pool_that_cannot_work(variable: str, value: str) -> None:
    loader = SQLAlchemyConfigLoader(sqlalchemy_source_stub(**{variable: value}))

    with pytest.raises(DatureConfigError) as excinfo:
        loader.load()

    assert variable in render_exception(excinfo.value)
