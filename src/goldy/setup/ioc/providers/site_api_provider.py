from collections.abc import AsyncIterator
from typing import Final

import httpx
from dishka import Provider, Scope

from goldy.application.commands.catalog.catalog_synchronizer import (
    CatalogSynchronizer,
)
from goldy.application.common.ports.catalog import CatalogSource
from goldy.infrastructure.adapters.catalog.site_catalog_source import (
    SiteCatalogSource,
)
from goldy.infrastructure.adapters.site_api.site_api_client import SiteApiClient
from goldy.setup.configs.site_api_config import SiteApiConfig


async def make_site_api_http_client(
    site_api_config: SiteApiConfig,
) -> AsyncIterator[httpx.AsyncClient]:
    """The worker's HTTP connection pool to the site, closed with the container.

    Redirects are not followed: the site's API answers its own paths without
    them, and a redirect is either a misconfigured URL or somebody else's
    server — following it would hand the Bearer token to wherever it points.
    The trailing slash on the base URL makes httpx append endpoint paths to
    ``/api/v1`` instead of replacing its last segment.
    """
    client = httpx.AsyncClient(
        base_url=site_api_config.base_url.strip().rstrip("/") + "/",
        timeout=site_api_config.timeout_seconds,
        follow_redirects=False,
    )
    try:
        yield client
    finally:
        await client.aclose()


def make_site_api_client(
    http_client: httpx.AsyncClient,
    site_api_config: SiteApiConfig,
) -> SiteApiClient:
    """The site API client, handed its token as a plain string.

    Infrastructure must not import setup, so the adapter never sees
    :class:`SiteApiConfig`; it is unpacked here.
    """
    return SiteApiClient(http_client, site_api_config.token)


def make_site_catalog_source(
    client: SiteApiClient,
    site_api_config: SiteApiConfig,
) -> CatalogSource:
    """The site as the worker's catalog source, paging at the configured size."""
    return SiteCatalogSource(client, site_api_config.page_size)


def site_api_provider() -> Provider:
    """The site tkgoldy.ru — the only bridge to 1C — and only the worker gets it.

    Its own group for the rule ``notifications_provider`` follows: it carries a
    secret, the site token, and a container is a statement about what a
    process may do. The bot has no business pulling a catalog or holding the
    key to the site's API; the seeder reads a file and binds ``CatalogSource``
    to it through ``catalog_source_provider`` instead.

    ``APP`` for what belongs to the process — the connection pool, the client
    that holds nothing but it and the token, and the stateless source.
    ``REQUEST`` for the synchronizer, which sends commands through the
    request's ``Sender`` and so lives as long as one task run.

    The client is bound on its own so the order outbox and linking, when they
    arrive, reuse this pool rather than open a second one.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.from_context(provides=SiteApiConfig, scope=Scope.APP)
    provider.provide(make_site_api_http_client, scope=Scope.APP)
    provider.provide(make_site_api_client, scope=Scope.APP)
    provider.provide(make_site_catalog_source, scope=Scope.APP)
    provider.provide(source=CatalogSynchronizer)
    return provider
