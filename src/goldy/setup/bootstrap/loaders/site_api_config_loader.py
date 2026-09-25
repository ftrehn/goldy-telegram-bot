from typing import TYPE_CHECKING, Final, override
from urllib.parse import urlsplit

from dature import V, load

from goldy.setup.bootstrap.loaders.consts import (
    CRON_FIELDS,
    LOCAL_SITE_API_HOSTS,
    SITE_API_PAGE_SIZE_MAX,
    SITE_API_PAGE_SIZE_MIN,
    SITE_API_TIMEOUT_MAX,
)
from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.configs.site_api_config import SiteApiConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


def _url_is_safe(config: SiteApiConfig) -> bool:
    """Whether the API root is an absolute URL the token may travel to.

    https anywhere; plain http only to a host where the request never leaves
    the machine. No query string and no fragment — the client appends paths
    to this root, and a ``?`` in the middle would swallow them.
    """
    try:
        parts = urlsplit(config.base_url.strip())
        host = parts.hostname
    except ValueError:
        return False

    if not host or parts.query or parts.fragment:
        return False

    if parts.scheme == "https":
        return True

    return parts.scheme == "http" and host in LOCAL_SITE_API_HOSTS


def _token_is_present(config: SiteApiConfig) -> bool:
    """A token with something in it and no whitespace to break the header."""
    token = config.token
    return bool(token) and not any(character.isspace() for character in token)


def _timeout_is_sane(config: SiteApiConfig) -> bool:
    return 0 < config.timeout_seconds <= SITE_API_TIMEOUT_MAX


def _page_size_is_allowed(config: SiteApiConfig) -> bool:
    return SITE_API_PAGE_SIZE_MIN <= config.page_size <= SITE_API_PAGE_SIZE_MAX


def _cron_has_five_fields(config: SiteApiConfig) -> bool:
    """A shape check only — taskiq parses the expression itself.

    Worth doing here anyway: a schedule taskiq cannot parse is logged by the
    scheduler and skipped, and the catalog then quietly stops updating.
    """
    return len(config.catalog_sync_cron.split()) == CRON_FIELDS


class SiteApiConfigLoader(ConfigLoader[SiteApiConfig]):
    """``dature``-backed loader for :class:`SiteApiConfig`.

    Every message names the variable, because the person reading it has a
    ``.env`` open, not this class. The token is masked: a startup failure is a
    log line, and the log must not carry the key to the site.
    """

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> SiteApiConfig:
        return load(
            self._source_factory.create(),
            schema=SiteApiConfig,
            root_validators=self._root_validators(),
            secret_field_names=("token",),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        local = ", ".join(sorted(LOCAL_SITE_API_HOSTS))
        return (
            V.root(
                _url_is_safe,
                error_message=(
                    "GOLDY_SITE_API_URL must be an https URL without a query, "
                    "such as https://tkgoldy.ru/api/v1; plain http is allowed "
                    f"only for {local}"
                ),
            ),
            V.root(
                _token_is_present,
                error_message=(
                    "GOLDY_SITE_API_TOKEN must hold the token the site issued, "
                    "without spaces"
                ),
            ),
            V.root(
                _timeout_is_sane,
                error_message=(
                    "GOLDY_SITE_API_TIMEOUT must be a positive number of seconds, "
                    f"at most {SITE_API_TIMEOUT_MAX:g}"
                ),
            ),
            V.root(
                _page_size_is_allowed,
                error_message=(
                    f"GOLDY_SITE_API_PAGE_SIZE must be between "
                    f"{SITE_API_PAGE_SIZE_MIN} and {SITE_API_PAGE_SIZE_MAX}"
                ),
            ),
            V.root(
                _cron_has_five_fields,
                error_message=(
                    "GOLDY_CATALOG_SYNC_CRON must be a five-field cron "
                    "expression, such as '*/15 * * * *'"
                ),
            ),
        )
