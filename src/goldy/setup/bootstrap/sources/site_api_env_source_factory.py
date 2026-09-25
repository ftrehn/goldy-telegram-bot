from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.site_api_config import SiteApiConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class SiteApiEnvSourceFactory(SourceFactory):
    """Maps the ``GOLDY_SITE_API_*`` variables onto :class:`SiteApiConfig`.

    Prefixed so none of them can collide with the environment at large — a
    bare ``API_URL`` or ``TIMEOUT`` is exactly the kind of name some base
    image already sets.
    """

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[SiteApiConfig].base_url: "GOLDY_SITE_API_URL",
                F[SiteApiConfig].token: "GOLDY_SITE_API_TOKEN",
                F[SiteApiConfig].timeout_seconds: "GOLDY_SITE_API_TIMEOUT",
                F[SiteApiConfig].page_size: "GOLDY_SITE_API_PAGE_SIZE",
                F[SiteApiConfig].catalog_sync_cron: "GOLDY_CATALOG_SYNC_CRON",
            },
        )
