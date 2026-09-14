from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.notification_config import NotificationConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class NotificationEnvSourceFactory(SourceFactory):
    """Maps the bot token onto :class:`NotificationConfig`.

    The same variable the bot reads. Notifications are sent into the
    conversation the customer already has with the shop, so they must come from
    that account — and a deployment that had to set the token twice would
    eventually set it twice differently.
    """

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[NotificationConfig].bot_token: "TELEGRAM_BOT_TOKEN",
            },
        )
