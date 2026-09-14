from typing import TYPE_CHECKING, Final, override

from dature import V, load

from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.configs.catalog_config import CatalogConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


def _price_type_is_named(config: CatalogConfig) -> bool:
    """Whether a default price list was actually configured.

    Checked at startup, because every other way of finding out is worse. An
    empty value would reach the pricing gateway as an identifier matching no
    row, and the first customer without a binding would be told their price
    list is not configured - a message about somebody else's mistake, delivered
    to the one person who cannot fix it.
    """
    return bool(config.default_price_type_id.strip())


class CatalogConfigLoader(ConfigLoader[CatalogConfig]):
    """``dature``-backed loader for :class:`CatalogConfig`."""

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> CatalogConfig:
        return load(
            self._source_factory.create(),
            schema=CatalogConfig,
            root_validators=self._root_validators(),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        return (
            V.root(
                _price_type_is_named,
                error_message=(
                    "GOLDY_DEFAULT_PRICE_TYPE_ID must name the price type "
                    "customers without a binding are shown"
                ),
            ),
        )
