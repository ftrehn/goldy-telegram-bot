from collections.abc import AsyncIterator
from typing import Final

import httpx
from dishka import Provider, Scope

from goldy.application.commands.catalog.catalog_synchronizer import (
    CatalogSynchronizer,
)
from goldy.application.commands.site.order_handover_runner import OrderHandoverRunner
from goldy.application.common.ports.catalog import CatalogSource
from goldy.application.common.ports.site import (
    SiteFinance,
    SiteLinking,
    SiteOrders,
    SitePricing,
)
from goldy.infrastructure.adapters.catalog.site_catalog_source import (
    SiteCatalogSource,
)
from goldy.infrastructure.adapters.site_api.site_api_client import SiteApiClient
from goldy.infrastructure.adapters.site_api.site_customer_adapters import (
    HttpSiteFinance,
    HttpSiteLinking,
    HttpSitePricing,
)
from goldy.infrastructure.adapters.site_api.site_orders_adapter import HttpSiteOrders
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
    """The site tkgoldy.ru — the only bridge to 1C — for the processes that talk to it.

    Its own group for the rule ``notifications_provider`` follows: it carries a
    secret, the site token, and a container is a statement about what a
    process may do. The bot gets it because linking, personal prices, finance
    and a customer's cancellation all ask the site on a person's behalf; the
    worker gets it to hand orders over and read their statuses back. The
    seeder does not: it reads a file and talks to nobody.

    Everything here is ``APP``-scoped: the connection pool, the client that
    holds nothing but it and the token, and four stateless adapters over it.
    """
    provider: Final[Provider] = Provider(scope=Scope.APP)
    provider.from_context(provides=SiteApiConfig, scope=Scope.APP)
    provider.provide(make_site_api_http_client)
    provider.provide(make_site_api_client)
    provider.provide(source=HttpSiteLinking, provides=SiteLinking)
    provider.provide(source=HttpSitePricing, provides=SitePricing)
    provider.provide(source=HttpSiteFinance, provides=SiteFinance)
    provider.provide(source=HttpSiteOrders, provides=SiteOrders)
    return provider


def site_sync_provider() -> Provider:
    """What the worker runs against the site on a schedule.

    The catalog pull and the order handover. ``REQUEST`` for the two runners,
    which send commands through the request's ``Sender`` and so live as long
    as one task run; ``APP`` for the stateless catalog source.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(make_site_catalog_source, scope=Scope.APP)
    provider.provide(source=CatalogSynchronizer)
    provider.provide(source=OrderHandoverRunner)
    return provider
