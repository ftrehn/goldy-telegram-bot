from typing import TYPE_CHECKING, Final, override

from dature import V, load

from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.configs.notification_config import NotificationConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


class NotificationConfigLoader(ConfigLoader[NotificationConfig]):
    """``dature``-backed loader for :class:`NotificationConfig`.

    The validator names the environment variable rather than the field, because
    the person reading the failure is deploying a worker and has a ``.env`` in
    front of them, not a dataclass. Without the token the worker starts
    perfectly well and then fails on the first order — at 401, in a log nobody
    is reading — so it refuses at startup instead.
    """

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> NotificationConfig:
        return load(
            self._source_factory.create(),
            schema=NotificationConfig,
            root_validators=self._root_validators(),
            secret_field_names=("bot_token",),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        return (
            V.root(
                lambda c: ":" in c.bot_token.strip(),
                error_message=(
                    "TELEGRAM_BOT_TOKEN must look like '<bot_id>:<secret>' — the "
                    "worker sends notifications as the same bot"
                ),
            ),
        )
