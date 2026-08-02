from dataclasses import dataclass
from typing import Final
from urllib.parse import quote

RABBITMQ_SCHEME: Final[str] = "amqp"
DEFAULT_VHOST: Final[str] = "/"


@dataclass(slots=True, frozen=True)
class RabbitMQConfig:
    """Connection settings for the RabbitMQ server behind taskiq and the outbox.

    Plain stdlib dataclass with no dependency on the config loader: the env
    mapping and validation live in
    ``goldy.setup.bootstrap.loaders.rabbitmq_config_loader``.

    Says *where* the broker is reached, and nothing about how work behaves once
    it gets there — that is :class:`TaskIQConfig`. The two are separated because
    queue naming and retry policy change per environment, while the host and
    credentials change per deployment.

    Attributes:
        host: RabbitMQ server hostname or IP address.
        port: AMQP port.
        user: Username. Required rather than defaulting to the built-in
            ``guest`` account: RabbitMQ only accepts ``guest`` over loopback, so
            a deployment that forgot to set it would fail on connect with a bare
            "access refused" instead of at startup with a readable message.
        password: Password for ``user``. Required for the same reason.
        vhost: Virtual host to connect to.

    Properties:
        uri: Complete ``amqp://`` connection URI.
    """

    host: str
    port: int
    user: str
    password: str
    vhost: str = DEFAULT_VHOST

    @property
    def uri(self) -> str:
        """Builds the AMQP connection URI.

        Every part that a user controls is percent-encoded. The virtual host in
        particular is a path segment, so the default ``/`` would otherwise read
        as an empty name and silently connect somewhere else — and a password
        containing ``@`` or ``/`` would corrupt the URI outright.
        """
        user = quote(self.user, safe="")
        password = quote(self.password, safe="")
        vhost = quote(self.vhost, safe="")

        return f"{RABBITMQ_SCHEME}://{user}:{password}@{self.host}:{self.port}/{vhost}"
