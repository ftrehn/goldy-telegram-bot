from typing import TYPE_CHECKING, Final, override

from dature import V, load

from goldy.domain.users.values.locale import SUPPORTED_LOCALES
from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.configs.telegram_config import TelegramConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


class TelegramConfigLoader(ConfigLoader[TelegramConfig]):
    """``dature``-backed loader for :class:`TelegramConfig`."""

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> TelegramConfig:
        return load(
            self._source_factory.create(),
            schema=TelegramConfig,
            root_validators=self._root_validators(),
            secret_field_names=("bot_token",),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        return (
            # Shape only, not validity — a token that looks right but was
            # revoked can only be found out by asking Telegram. Catching the
            # empty and obviously-malformed cases here still turns the
            # commonest deployment mistake into a readable startup error
            # instead of a 401 from getUpdates.
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
        )
