from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.catalog_config import CatalogConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class CatalogEnvSourceFactory(SourceFactory):
    """Maps ``GOLDY_DEFAULT_PRICE_TYPE_ID`` onto :class:`CatalogConfig`."""

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[CatalogConfig].default_price_type_id: "GOLDY_DEFAULT_PRICE_TYPE_ID",
            },
        )
