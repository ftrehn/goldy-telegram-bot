"""The ``/start`` payload behind a "buy in Telegram" link, in both directions.

A link on a product page of the shop's website has to open the bot on that
product's card. Telegram carries exactly one thing across from such a link: the
text after ``/start``, at most 64 characters long and spelled in
``[A-Za-z0-9_-]``. Everything here follows from that budget.

The identifiers the catalog is keyed by come from 1C and are text of up to 128
characters — see :class:`~goldy.domain.catalog.values.source_id.SourceId` —
today a 36-character GUID and, once product variants are switched on, possibly
the ``guid#guid`` composite ADR-0002 describes. Neither the ``#`` nor, in
general, whatever else 1C puts inside one belongs to Telegram's alphabet, so an
identifier cannot travel as itself.

A payload is therefore a kind letter, an underscore, and the identifier encoded
as base64url without padding: ``p_U0tVLTEyMzQ`` opens a product and
``c_Q0FULTE`` opens a category.

Base64url rather than anything denser, and the choice is about exactness rather
than about size. The decoded identifier is looked up by equality in a
projection this service does not own, so it has to come back byte for byte —
and every scheme that would pack a GUID into sixteen bytes must first normalise
its case and its dashes, handing back an identifier that *looks* right and
matches nothing. Base64url round-trips arbitrary bytes and leaves the question
of what counts as an identifier where it belongs, which is in 1C.

The price of that is a ceiling. Sixty-two characters of body encode 46 bytes,
so an identifier longer than that has no link at all: a GUID spends 36 of them
and the composite key would spend 73. :func:`encode_payload` refuses loudly
there rather than truncating, because a truncated identifier is not a shorter
link, it is a link that opens the wrong screen or none.

The alternative design, and why it lost: mint a short opaque token, store the
target in a table, hand out ``t_a7f3``. That fits an identifier of any length
and it costs a table, a migration, and a round trip to this service every time
the website wants a link — where the encoding here is derivable offline by
anybody holding the product identifier, which is exactly what an export to the
site needs.

Nothing is signed. A payload names a public catalog item and grants nothing, so
a forged one either fails to decode or names a product that does not exist, and
both land the visitor on the catalog with a sentence saying so. A signature
would be protecting a customer from reaching a product they are already free to
browse.

A new kind takes a new letter and never takes over an old one. That is the whole
compatibility rule: links printed on a website outlive every deploy, and a
letter that changes meaning turns them into links to the wrong thing. A letter
this bot does not know yet reads as a link that does not work here, which is
the right answer for an old bot meeting a new link.
"""

import base64
import binascii
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from aiogram import Bot

from goldy.presentation.telegram.errors import (
    BotWithoutUsernameError,
    DeepLinkPayloadTooLongError,
)

MAX_PAYLOAD_LENGTH: Final[int] = 64
"""What Telegram carries after ``/start``, and the source of every limit here."""

SEPARATOR: Final[str] = "_"
"""One character between the kind and the body, spendable because it is cheap.

``_`` also belongs to the base64url alphabet, which costs nothing: the kind is
exactly one character wide, so the split is by position rather than by search
and a body full of underscores parses the same as any other.
"""

PAYLOAD_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"\A[A-Za-z0-9_-]{{1,{MAX_PAYLOAD_LENGTH}}}\Z",
)
"""What Telegram promises a deep link carries, checked rather than trusted.

``/start`` is also a command anybody may type by hand with anything at all
after it — a path, a quotation mark, four kilobytes of text — and this runs
before anything else looks at the payload.
"""

LINK_TEMPLATE: Final[str] = "https://t.me/{username}/?start={payload}"


class DeepLinkKind(StrEnum):
    """What a link points at, one letter each.

    The letters are part of every link ever printed, so they are append-only:
    a new kind takes an unused letter and no existing one is ever moved.
    """

    PRODUCT = "p"
    CATEGORY = "c"


@dataclass(frozen=True, slots=True)
class DeepLinkTarget:
    """The thing a link names, once its payload has been read.

    Text rather than a ``ProductId`` or a ``CategoryId``: presentation has no
    business minting a domain value out of something a stranger typed, and the
    queries this feeds take the identifier as text for the same reason.
    """

    kind: DeepLinkKind
    id: str


def encode_payload(target: DeepLinkTarget) -> str:
    """Spells the text a link puts after ``/start``.

    Raises:
        DeepLinkPayloadTooLongError: the identifier does not fit, which starts
            at 47 bytes of identifier and is loud on purpose — a link built
            from a truncated identifier opens the wrong product or none.
    """
    body = base64.urlsafe_b64encode(target.id.encode()).decode().rstrip("=")
    payload = f"{target.kind.value}{SEPARATOR}{body}"

    if len(payload) > MAX_PAYLOAD_LENGTH:
        msg = (
            f"'{target.id}' encodes to a payload of {len(payload)} characters, "
            f"and Telegram carries {MAX_PAYLOAD_LENGTH} after /start."
        )
        raise DeepLinkPayloadTooLongError(msg)

    return payload


def decode_payload(payload: str | None) -> DeepLinkTarget | None:
    """Reads a payload back, answering ``None`` for anything it cannot.

    One ``None`` covers every way of failing — no payload at all, a payload
    outside Telegram's alphabet, an unknown kind letter, a body that is not
    base64, bytes that are not text, an identifier that is only whitespace —
    because the caller does the same thing in all six cases. What the visitor
    is owed is the catalog and one sentence; which of the six it was is our
    business rather than theirs, and the log's.

    Forgery needs no separate branch and gets none. A payload nobody could have
    minted either fails one of those checks or decodes to an identifier the
    catalog has never heard of, and the second is the same case as a product
    withdrawn between the link being printed and the link being followed.
    """
    if payload is None or PAYLOAD_PATTERN.match(payload) is None:
        return None

    kind, separator, body = payload.partition(SEPARATOR)

    if not separator or not body:
        return None

    try:
        target_kind = DeepLinkKind(kind)
    except ValueError:
        return None

    identifier = _decode_body(body)

    return None if identifier is None else DeepLinkTarget(kind=target_kind, id=identifier)


def deeplink_url(bot_username: str, payload: str) -> str:
    """The link itself, ready to be put behind a button on a web page."""
    return LINK_TEMPLATE.format(username=bot_username, payload=payload)


async def product_deeplink(bot: Bot, product_id: str) -> str:
    """The "buy in Telegram" link for one product.

    The function the export to the website is meant to call, and the one a
    manager sending a customer a product is meant to call, so that neither
    hand-assembles a URL out of a bot name they happen to remember.
    """
    return await _deeplink(bot, DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id=product_id))


async def category_deeplink(bot: Bot, category_id: str) -> str:
    """The same, for a section of the catalog rather than a single product."""
    return await _deeplink(
        bot,
        DeepLinkTarget(kind=DeepLinkKind.CATEGORY, id=category_id),
    )


async def _deeplink(bot: Bot, target: DeepLinkTarget) -> str:
    """Asks Telegram what this bot is called, then spells the link.

    The name comes from ``Bot.me()`` and never from configuration. The username
    belongs to Telegram and can be changed there without anybody editing an
    environment variable, and a configured copy that has gone stale does not
    produce a broken link — it produces a working link into somebody else's
    bot. ``Bot.me()`` caches the answer for the life of the process, so an
    export of ten thousand links costs one call.

    Raises:
        BotWithoutUsernameError: Telegram returned an account with no username,
            which no link can address.
    """
    me = await bot.me()

    if me.username is None:
        msg = "This bot has no username, so no deep link can point at it."
        raise BotWithoutUsernameError(msg)

    return deeplink_url(me.username, encode_payload(target))


def _decode_body(body: str) -> str | None:
    """The identifier inside the body, or ``None`` if it is not one.

    Padding is put back rather than carried: ``=`` is outside Telegram's
    alphabet, so a payload cannot hold it and the length it stands for is
    recoverable from the body itself.
    """
    padded = body + "=" * (-len(body) % 4)

    try:
        raw = base64.urlsafe_b64decode(padded)
    except binascii.Error, ValueError:
        return None

    try:
        identifier = raw.decode()
    except UnicodeDecodeError:
        return None

    return identifier if identifier.strip() else None
