"""The payload a link from the website carries, encoded and read back.

Nothing else in the project checks this. A payload is minted by an export the
shop runs and read by a bot the shop deploys, and the two never meet in a test
run — so a codec that quietly drops the last byte would show up as customers
landing on the catalog instead of on the product they tapped, months later and
attributed to Telegram.
"""

from typing import Any

import pytest
from aiogram import Bot
from aiogram.types import User

from goldy.presentation.telegram.common.deeplinks import (
    MAX_PAYLOAD_LENGTH,
    PAYLOAD_PATTERN,
    DeepLinkKind,
    DeepLinkTarget,
    category_deeplink,
    decode_payload,
    encode_payload,
    product_deeplink,
)
from goldy.presentation.telegram.errors import (
    BotWithoutUsernameError,
    DeepLinkPayloadTooLongError,
)

GUID = "9b2f5c1e-7a43-4d8e-9f10-6c3b2a1d0e5f"
"""The shape every identifier in the catalog has today, spelled out in full."""

BOT_USERNAME = "goldy_bot"
BOT_TOKEN = "42:TEST"

AWKWARD_IDENTIFIERS = (
    GUID,
    "40-1234",
    "a" * 46,
    "Пальто/зимнее #7",
    "id with spaces",
    "slash/and+plus=sign",
    "_-_-_-",
)
"""Identifiers chosen for the ways they could break the alphabet, not the shop.

1C is asked for nothing and promises nothing: the projection stores whatever
arrives, up to 128 characters of it. Cyrillic checks that the payload survives
text that is not ASCII at all, and the last three check the three characters
base64 and URLs each treat as punctuation of their own.
"""


@pytest.mark.parametrize("identifier", AWKWARD_IDENTIFIERS)
@pytest.mark.parametrize("kind", tuple(DeepLinkKind))
def test_a_target_survives_the_round_trip_unchanged(
    kind: DeepLinkKind,
    identifier: str,
) -> None:
    """Byte for byte, because the identifier is looked up by equality.

    An identifier that comes back nearly right is worse than one that fails to
    decode: it names nothing in the projection, so the customer is told the
    product is gone while it sits in the catalog.
    """
    target = DeepLinkTarget(kind=kind, id=identifier)

    assert decode_payload(encode_payload(target)) == target


@pytest.mark.parametrize("identifier", AWKWARD_IDENTIFIERS)
def test_a_payload_is_spelled_the_way_telegram_demands(identifier: str) -> None:
    """64 characters of ``[A-Za-z0-9_-]``, and Telegram enforces it, not us.

    A payload one character outside that is not a link that fails at our end —
    Telegram refuses to open it at all, and the person who tapped it sees the
    bot's profile instead of a product.
    """
    payload = encode_payload(DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id=identifier))

    assert PAYLOAD_PATTERN.match(payload) is not None
    assert len(payload) <= MAX_PAYLOAD_LENGTH


def test_a_guid_leaves_room_to_spare() -> None:
    """The one measurement the whole scheme was chosen against.

    Every identifier in the catalog is a GUID today. If that did not fit, the
    encoding would be the wrong encoding rather than a limitation, so this is
    pinned rather than assumed.
    """
    payload = encode_payload(DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id=GUID))

    assert len(payload) < MAX_PAYLOAD_LENGTH


def test_the_kinds_are_told_apart() -> None:
    """A product link and a category link must not decode to each other."""
    product = decode_payload(
        encode_payload(DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id=GUID)),
    )
    category = decode_payload(
        encode_payload(DeepLinkTarget(kind=DeepLinkKind.CATEGORY, id=GUID)),
    )

    assert product is not None
    assert category is not None
    assert product.kind is DeepLinkKind.PRODUCT
    assert category.kind is DeepLinkKind.CATEGORY


def test_an_identifier_too_long_to_encode_is_refused_loudly() -> None:
    """Because the alternative is a link that opens the wrong product.

    47 bytes is where the 64 characters run out. Truncating there would produce
    a perfectly valid payload naming a perfectly wrong thing, and nothing
    downstream could tell.
    """
    target = DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id="a" * 47)

    with pytest.raises(DeepLinkPayloadTooLongError):
        encode_payload(target)


@pytest.mark.parametrize(
    ("payload", "why"),
    (
        (None, "no deep link at all"),
        ("", "an empty payload"),
        ("p", "a kind with no body"),
        ("p_", "a separator with no body"),
        ("_QUJD", "a body with no kind"),
        ("x_QUJD", "a kind this bot has never heard of"),
        ("p_QUJ$", "a character outside Telegram's alphabet"),
        ("p_QUJDR", "a body whose length is not valid base64"),
        ("p_gA", "bytes that are not text"),
        ("p_ICAg", "an identifier made of spaces"),
        ("/start p_QUJD", "the whole command pasted in as the payload"),
        ("p_" + "A" * 100, "a payload longer than Telegram would carry"),
    ),
)
def test_rubbish_and_forgery_decode_to_nothing(payload: str | None, why: str) -> None:
    """All twelve are the same case for the caller, and this is why they may be.

    Nothing here is trusted. ``/start`` is a command anybody can type by hand
    with anything after it, and a payload can be edited in a browser's address
    bar by somebody who wants to see what happens — so the checks run before
    anything reads what came out, and every failure is the same ``None``.
    """
    assert decode_payload(payload) is None, why


def test_a_forged_payload_that_parses_is_left_to_the_catalog() -> None:
    """Because a well-formed payload naming nothing is not a codec's problem.

    Anybody can base64 a string of their own and get a payload this reads
    perfectly. There is nothing to detect: the result is an identifier the
    projection has never heard of, which is the same case as a product
    withdrawn between the link being printed and the link being followed, and
    it is answered by the catalog rather than here.
    """
    forged = decode_payload(
        encode_payload(DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id="made-up"))
    )

    assert forged == DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id="made-up")


async def test_a_product_link_is_built_from_the_name_telegram_reports() -> None:
    """Not from configuration, which is the point of the whole function.

    A configured username that has gone stale does not produce a broken link.
    It produces a working link into whichever bot now holds that name.
    """
    bot = _bot_called(BOT_USERNAME)

    link = await product_deeplink(bot, GUID)

    assert link.startswith(f"https://t.me/{BOT_USERNAME}/?start=")
    assert decode_payload(link.rsplit("=", maxsplit=1)[1]) == DeepLinkTarget(
        kind=DeepLinkKind.PRODUCT,
        id=GUID,
    )


async def test_a_category_link_opens_a_section_rather_than_a_product() -> None:
    bot = _bot_called(BOT_USERNAME)

    link = await category_deeplink(bot, GUID)

    assert decode_payload(link.rsplit("=", maxsplit=1)[1]) == DeepLinkTarget(
        kind=DeepLinkKind.CATEGORY,
        id=GUID,
    )


async def test_a_bot_with_no_username_cannot_be_linked_to() -> None:
    """Impossible for a bot BotFather made, and still not left to chance.

    Unchecked, the ``None`` renders into the URL and an export writes
    ``https://t.me/None/?start=…`` onto a live product page, where nothing
    fails until a customer taps it.
    """
    bot = _bot_called(None)

    with pytest.raises(BotWithoutUsernameError):
        await product_deeplink(bot, GUID)


def _bot_called(username: str | None) -> Bot:
    """A real ``Bot`` whose ``me()`` is already answered, so nothing is sent.

    ``Bot.me`` caches the reply to ``getMe`` and only calls Telegram when the
    cache is empty — filling it is what turns a network call into a local one
    without replacing the class every other part of aiogram expects.
    """
    bot = Bot(token=BOT_TOKEN)
    cached: Any = bot
    cached._me = User(id=42, is_bot=True, first_name="Goldy", username=username)

    return bot
