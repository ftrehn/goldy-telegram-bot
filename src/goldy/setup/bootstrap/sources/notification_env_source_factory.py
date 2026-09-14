from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.notification_config import NotificationConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class NotificationEnvSourceFactory(SourceFactory):
    """Maps the bot token and the proxy onto :class:`NotificationConfig`.

    The same variables the bot reads. Notifications are sent into the
    conversation the customer already has with the shop, so they must come from
    that account — and a deployment that had to set the token twice would
    eventually set it twice differently. The proxy follows the token: both
    processes reach Telegram from the same place, so they leave through the
    same door.
    """

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[NotificationConfig].bot_token: "TELEGRAM_BOT_TOKEN",
                F[NotificationConfig].proxy_url: "TELEGRAM_PROXY_URL",
            },
        )
