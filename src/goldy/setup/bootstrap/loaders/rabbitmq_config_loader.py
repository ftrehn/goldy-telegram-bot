from typing import TYPE_CHECKING, Final, override

from dature import V, load

from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.configs.rabbitmq_config import RabbitMQConfig

from .consts import PORT_MAX, PORT_MIN

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


class RabbitMQConfigLoader(ConfigLoader[RabbitMQConfig]):
    """``dature``-backed loader for :class:`RabbitMQConfig`."""

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> RabbitMQConfig:
        return load(
            self._source_factory.create(),
            schema=RabbitMQConfig,
            root_validators=self._root_validators(),
            secret_field_names=("password",),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        return (
            V.root(
                lambda c: bool(c.host.strip()),
                error_message="RABBITMQ_HOST must not be empty",
            ),
            V.root(
                lambda c: PORT_MIN <= c.port <= PORT_MAX,
                error_message=(
                    f"RABBITMQ_PORT must be between {PORT_MIN} and {PORT_MAX}"
                ),
            ),
            V.root(
                lambda c: bool(c.vhost),
                error_message=(
                    "RABBITMQ_VHOST must not be empty — use '/' for the default "
                    "virtual host"
                ),
            ),
            # A blank username would be sent as an empty SASL identity and the
            # server would refuse the connection with a bare "access refused",
            # which is a miserable thing to debug at startup.
            V.root(
                lambda c: bool(c.user),
                error_message="RABBITMQ_USER must not be empty",
            ),
        )
