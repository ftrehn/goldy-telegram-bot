from typing import Final

PORT_MIN: Final[int] = 1
PORT_MAX: Final[int] = 65535

POOL_SIZE_MIN: Final[int] = 1
POOL_SIZE_MAX: Final[int] = 1000
POOL_RECYCLE_MIN: Final[int] = 1
POOL_OVERFLOW_MIN: Final[int] = 0

REDIS_DB_MIN: Final[int] = 0
REDIS_DB_MAX: Final[int] = 15
DISTINCT_REDIS_DATABASES: Final[int] = 4
"""Results, schedules, cache and bot dialogue state must not share an index."""

RETRY_COUNT_MIN: Final[int] = 0
DELAY_MIN: Final[float] = 0.0
MAX_DELAY_EXPONENT_MIN: Final[float] = 1.0
QOS_MIN: Final[int] = 1

TEMPERATURE_MIN: Final[float] = 0.0
TEMPERATURE_MAX: Final[float] = 2.0

SITE_API_PAGE_SIZE_MIN: Final[int] = 1
SITE_API_PAGE_SIZE_MAX: Final[int] = 1000
"""The bounds the site's ``/catalog/items`` accepts for ``limit``."""
SITE_API_TIMEOUT_MAX: Final[float] = 600.0
CRON_FIELDS: Final[int] = 5
LOCAL_SITE_API_HOSTS: Final[frozenset[str]] = frozenset(
    {"localhost", "127.0.0.1", "::1", "host.docker.internal", "tkgoldy_web"},
)
"""Hosts the site API may be reached over plain http.

Loopback, the docker host, and the site's own container on a shared docker
network — the same exception the site makes for its token, because none of
these carry the request off the machine.
"""
