from typing import TYPE_CHECKING, Final, override

from dature import V, load

from goldy.domain.users.values.locale import SUPPORTED_LOCALES
from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.bootstrap.loaders.telegram_proxy_url import (
    TELEGRAM_PROXY_URL_ERROR,
    is_telegram_proxy_url,
)
from goldy.setup.configs.telegram_config import TelegramConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


class TelegramConfigLoader(ConfigLoader[TelegramConfig]):
    """``dature``-backed loader for :class:`TelegramConfig`.

    The proxy URL is a secret field alongside the token: the password to the
    proxy lives inside it, and a startup failure is a log.
    """

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> TelegramConfig:
        return load(
            self._source_factory.create(),
            schema=TelegramConfig,
            root_validators=self._root_validators(),
            secret_field_names=("bot_token", "proxy_url"),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        return (
            V.root(
                lambda c: ":" in c.bot_token.strip(),
                error_message=("TELEGRAM_BOT_TOKEN must look like '<bot_id>:<secret>'"),
            ),
            V.root(
                lambda c: c.default_locale in SUPPORTED_LOCALES,
                error_message=(
                    f"TELEGRAM_DEFAULT_LOCALE must be one of: "
                    f"{', '.join(sorted(SUPPORTED_LOCALES))}"
                ),
            ),
            V.root(
                lambda c: c.fsm_ttl_seconds > 0,
                error_message="TELEGRAM_FSM_TTL_SECONDS must be a positive number",
            ),
            V.root(
                lambda c: is_telegram_proxy_url(c.proxy_url),
                error_message=TELEGRAM_PROXY_URL_ERROR,
            ),
        )
