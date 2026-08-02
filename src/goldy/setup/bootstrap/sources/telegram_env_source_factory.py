from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.telegram_config import TelegramConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class TelegramEnvSourceFactory(SourceFactory):
    """Maps ``TELEGRAM_*`` environment variables onto :class:`TelegramConfig`."""

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[TelegramConfig].bot_token: "TELEGRAM_BOT_TOKEN",
                F[TelegramConfig].use_redis_storage: "TELEGRAM_USE_REDIS_STORAGE",
                F[
                    TelegramConfig
                ].use_redis_event_isolation: "TELEGRAM_USE_REDIS_EVENT_ISOLATION",
                F[TelegramConfig].use_i18n_isolation: "TELEGRAM_USE_I18N_ISOLATION",
                F[TelegramConfig].default_locale: "TELEGRAM_DEFAULT_LOCALE",
                F[TelegramConfig].drop_pending_updates: "TELEGRAM_DROP_PENDING_UPDATES",
            },
        )
