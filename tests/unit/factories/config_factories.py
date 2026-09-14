"""Object mothers for the already-built configs, bypassing the loaders."""

from goldy.setup.configs.catalog_receiver_config import CatalogReceiverConfig
from goldy.setup.configs.postgres_config import PostgresConfig
from goldy.setup.configs.rabbitmq_config import RabbitMQConfig
from goldy.setup.configs.redis_config import RedisConfig


def create_postgres_config(
    *,
    user: str = "app",
    password: str = "s3cr3t",
    host: str = "localhost",
    port: int = 5432,
    db_name: str = "goldy",
    driver: str = "asyncpg",
) -> PostgresConfig:
    """Object mother for a valid :class:`PostgresConfig`."""
    return PostgresConfig(
        user=user,
        password=password,
        host=host,
        port=port,
        db_name=db_name,
        driver=driver,
    )


def create_redis_config(
    *,
    host: str = "localhost",
    port: int = 6379,
    user: str = "",
    password: str = "",
) -> RedisConfig:
    """Object mother for a valid :class:`RedisConfig`."""
    return RedisConfig(host=host, port=port, user=user, password=password)


def create_rabbitmq_config(
    *,
    host: str = "localhost",
    port: int = 5672,
    user: str = "guest",
    password: str = "guest",
    vhost: str = "/",
) -> RabbitMQConfig:
    """Object mother for a valid :class:`RabbitMQConfig`."""
    return RabbitMQConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        vhost=vhost,
    )


def create_catalog_receiver_config(
    *,
    token: str = "test-catalog-token-0123456789abcdefghij",
    host: str = "127.0.0.1",
    port: int = 8090,
    max_body_mib: int = 64,
) -> CatalogReceiverConfig:
    """Object mother for a valid :class:`CatalogReceiverConfig`.

    Loopback, the same as the config's own default, and spelled out anyway: a
    test that ever starts a site on this config must not open a port to the
    network, and that must stay true if the default is ever changed.
    """
    return CatalogReceiverConfig(
        token=token,
        host=host,
        port=port,
        max_body_mib=max_body_mib,
    )


# TaskIQConfig has a default for every field, so it needs no object mother —
# ``TaskIQConfig(queue_name="other")`` already reads as one.
