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

RECEIVER_TOKEN_MIN_LENGTH: Final[int] = 32
"""Short enough to type into a 1C constant, long enough that guessing is not a plan."""
RECEIVER_MAX_BODY_MIB_MIN: Final[int] = 1

TELEGRAM_PROXY_SCHEMES: Final[frozenset[str]] = frozenset({"http", "socks4", "socks5"})
"""The schemes ``aiohttp-socks`` parses — what aiogram's session hands a proxy URL to.

``https://`` and ``socks5h://`` are not among them: the library refuses both
with a ``ValueError`` at session construction, which the loader turns into a
startup error naming the variable instead.
"""
