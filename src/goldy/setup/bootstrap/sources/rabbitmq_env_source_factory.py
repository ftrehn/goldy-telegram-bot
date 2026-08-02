from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.rabbitmq_config import RabbitMQConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class RabbitMQEnvSourceFactory(SourceFactory):
    """Maps ``RABBITMQ_*`` environment variables onto :class:`RabbitMQConfig`."""

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[RabbitMQConfig].host: "RABBITMQ_HOST",
                F[RabbitMQConfig].port: "RABBITMQ_PORT",
                F[RabbitMQConfig].user: "RABBITMQ_USER",
                F[RabbitMQConfig].password: "RABBITMQ_PASSWORD",
                F[RabbitMQConfig].vhost: "RABBITMQ_VHOST",
            },
        )
