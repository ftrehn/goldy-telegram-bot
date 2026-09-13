from typing import TYPE_CHECKING, Final, override

from dature import V, load

from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.configs.catalog_receiver_config import CatalogReceiverConfig

from .consts import (
    PORT_MAX,
    PORT_MIN,
    RECEIVER_MAX_BODY_MIB_MIN,
    RECEIVER_TOKEN_MIN_LENGTH,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


def _token_is_long_enough(config: CatalogReceiverConfig) -> bool:
    """Whether the token is something worth comparing against.

    Measured after ``strip()`` because the value is pasted into a ``.env`` on
    one side and into a 1C constant on the other, and both sides compare it
    stripped: the 1C module trims its constant, and the receiver strips both
    the token it keeps and the one presented. A stray space is therefore
    harmless, and the only thing left for this check to refuse is a token
    that is padded to the minimum with whitespace.
    """
    return len(config.token.strip()) >= RECEIVER_TOKEN_MIN_LENGTH


class CatalogReceiverConfigLoader(ConfigLoader[CatalogReceiverConfig]):
    """``dature``-backed loader for :class:`CatalogReceiverConfig`.

    The messages name the environment variable rather than the field, because
    the person reading them is deploying the receiver with a ``.env`` in front
    of them. The token is validated at startup for the same reason the
    notifier's is: without one the process would listen perfectly well and
    refuse every batch 1C sends, in a log on a different machine from the one
    showing the error.
    """

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> CatalogReceiverConfig:
        return load(
            self._source_factory.create(),
            schema=CatalogReceiverConfig,
            root_validators=self._root_validators(),
            secret_field_names=("token",),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        return (
            V.root(
                _token_is_long_enough,
                error_message=(
                    "GOLDY_CATALOG_RECEIVER_TOKEN must be at least "
                    f"{RECEIVER_TOKEN_MIN_LENGTH} characters — it is the only "
                    "thing between the network and the catalog"
                ),
            ),
            V.root(
                lambda c: PORT_MIN <= c.port <= PORT_MAX,
                error_message=(
                    f"GOLDY_CATALOG_RECEIVER_PORT must be between {PORT_MIN} "
                    f"and {PORT_MAX}"
                ),
            ),
            V.root(
                lambda c: c.max_body_mib >= RECEIVER_MAX_BODY_MIB_MIN,
                error_message=(
                    "GOLDY_CATALOG_RECEIVER_MAX_BODY_MIB must be at least "
                    f"{RECEIVER_MAX_BODY_MIB_MIN} — a smaller ceiling refuses "
                    "every batch 1C sends"
                ),
            ),
        )
