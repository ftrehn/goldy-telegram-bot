from dataclasses import dataclass

DEFAULT_SITE_API_TIMEOUT_SECONDS = 30.0
DEFAULT_SITE_API_PAGE_SIZE = 500
DEFAULT_CATALOG_SYNC_CRON = "*/15 * * * *"


@dataclass(slots=True, frozen=True)
class SiteApiConfig:
    """How the worker reaches the site tkgoldy.ru, the only bridge to 1C.

    ADR-0004: the bot talks to 1C through nobody but the site, and the site's
    contract lives in its own repository as ``docs/API.md``. Loaded only by
    the worker and the scheduler, like :class:`NotificationConfig` and for the
    same reason: the token is a secret, and the shared bundle would put it
    within reach of the bot process, which has no business pulling a catalog.

    Attributes:
        base_url: The API root, ``https://tkgoldy.ru/api/v1``. Required, with
            no default: a worker pointed at the wrong site would sweep the
            projection down to whatever that site answered. Must be https —
            the token travels in a header — unless the host is a local or
            same-server docker address where the traffic never leaves the
            machine, which is the same exception the site itself makes.
        token: The client token the site issued (``tkg_…``), sent as a Bearer
            header. Required and masked in startup errors.
        timeout_seconds: How long one request may take, connect and read
            together. Generous rather than tight: a page of 500 items is
            assembled from several tables on the site, and a timeout that
            fires on a healthy site turns every sync into a retry storm.
        page_size: Items per page of ``/catalog/items``, 1 to 1000 as the site
            allows. It is also the size of one import transaction, which is
            why the ceiling matters: a product row binds fourteen parameters
            and Postgres refuses a statement past 32 767 of them.
        catalog_sync_cron: When the scheduler fires the catalog pull. Every
            fifteen minutes by default — the site's own stock and prices move
            with its 1C exchange, not faster, and a full pass of a few
            thousand rows is not free for either side.
    """

    base_url: str
    token: str
    timeout_seconds: float = DEFAULT_SITE_API_TIMEOUT_SECONDS
    page_size: int = DEFAULT_SITE_API_PAGE_SIZE
    catalog_sync_cron: str = DEFAULT_CATALOG_SYNC_CRON
