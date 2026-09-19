"""A link from the shop's website, followed all the way to a screen.

The unit tests around deep links cover the payload and the decision about which
window to open. Neither can say whether the window actually appears, and that
is the half that has broken before in this project: a dialog that is not
attached, a state group nobody registered, a handler aiogram never reaches
because a broader filter sat above it. Every one of those type-checks.

So these feed a real update into the real dispatcher — the auth gate, i18n, the
router filters, the mediator, Postgres — and read what the bot put on screen.
"""

import pytest

from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.deeplinks import (
    DeepLinkKind,
    DeepLinkTarget,
    encode_payload,
)
from tests.integration.arrange import CommandSender
from tests.integration.scenarios.shop import a_shop
from tests.integration.telegram.arrange import (
    PersonRegistrar,
    TextRenderer,
    UpdateFeeder,
)
from tests.integration.telegram.personas import a_stranger
from tests.integration.telegram.sent import SentCalls
from tests.unit.factories.catalog_factories import (
    make_category_id,
    make_product_id_value,
)

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

PRODUCT_NAME = "Product 1"
CATEGORY_NAME = "Group 1"


async def test_a_customer_following_a_product_link_lands_on_its_card(
    register_person: PersonRegistrar,
    send_worker_command: CommandSender,
    feed: UpdateFeeder,
    sent: SentCalls,
) -> None:
    """The feature, stated end to end and in one assertion.

    Nothing short of this says it: the payload can decode perfectly and the
    card still never appear, because whether ``CommandStart(deep_link=True)``
    is tried before the plain greeting is a property of the router rather than
    of any function under test.
    """
    person = await register_person()
    await send_worker_command(ImportCatalogCommand(snapshot=a_shop()))

    await feed(person.says(f"/start {_product_payload(1)}"))

    assert PRODUCT_NAME in sent.last_text()


async def test_a_stranger_registers_first_and_then_gets_what_they_came_for(
    send_worker_command: CommandSender,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """The whole point of storing the intent, and the only proof it survives.

    Two updates separate the link from the screen, with a phone number in
    between, and the failure this guards against is silent: the registration
    works, the welcome arrives, and the product the person actually came for is
    simply forgotten. Nobody would see an error.
    """
    stranger = a_stranger()
    await send_worker_command(ImportCatalogCommand(snapshot=a_shop()))

    await feed(stranger.says(f"/start {_product_payload(1)}"))
    assert sent.last_text() == text(text_keys.AUTH_REGISTRATION_REQUIRED)

    await feed(stranger.shares_contact())

    assert text(text_keys.START_WELCOME, name=stranger.first_name) in sent.texts()
    assert PRODUCT_NAME in sent.last_text()


async def test_an_ordinary_registration_still_ends_at_the_welcome(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Nobody followed a link, so nothing opens — the guard on the test above.

    Without this, a handler that opened the catalog for every new customer
    would pass every other test here and change what registration does for
    everybody who never saw the website.
    """
    stranger = a_stranger()

    await feed(stranger.shares_contact())

    assert sent.last_text() == text(text_keys.START_WELCOME, name=stranger.first_name)


async def test_a_link_to_a_product_that_is_gone_opens_the_catalog_and_says_why(
    register_person: PersonRegistrar,
    send_worker_command: CommandSender,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """A stale link is the ordinary state of a link, not an exception.

    Products are printed onto web pages and withdrawn from 1C months apart, so
    what matters is that the visitor gets a sentence and a shop rather than a
    refusal — a stranger's first contact with this bot must not be an error
    message.
    """
    person = await register_person()
    await send_worker_command(ImportCatalogCommand(snapshot=a_shop()))

    await feed(person.says(f"/start {_product_payload(404)}"))

    assert text(text_keys.DEEPLINK_PRODUCT_GONE) in sent.texts()
    assert text(text_keys.CATALOG_TITLE) in sent.last_text()


async def test_a_forged_payload_is_answered_like_any_other_dead_link(
    register_person: PersonRegistrar,
    send_worker_command: CommandSender,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Nothing is signed, and this is what that decision looks like in practice.

    A payload anybody can type after ``/start`` names either nothing readable
    or a product that does not exist. Both end on the catalog, which is also
    what makes the absence of a signature harmless: there is nothing behind a
    deep link that a registered customer could not reach by browsing.
    """
    person = await register_person()
    await send_worker_command(ImportCatalogCommand(snapshot=a_shop()))

    await feed(person.says("/start not-a-real-payload"))

    assert text(text_keys.DEEPLINK_PRODUCT_GONE) in sent.texts()
    assert text(text_keys.CATALOG_TITLE) in sent.last_text()


async def test_a_link_to_a_section_opens_the_catalog_standing_inside_it(
    register_person: PersonRegistrar,
    send_worker_command: CommandSender,
    feed: UpdateFeeder,
    sent: SentCalls,
) -> None:
    """The breadcrumb is handed over at start, having been walked by nobody.

    Everywhere else the tree is entered one tap at a time and the heading comes
    from the crumb those taps left behind. A link has no taps behind it, so
    this is the one path where the first crumb is supplied rather than built —
    and a screen headed by an empty name is what getting it wrong looks like.
    """
    person = await register_person()
    await send_worker_command(ImportCatalogCommand(snapshot=a_shop()))

    await feed(person.says(f"/start {_category_payload(1)}"))

    assert CATEGORY_NAME in sent.last_text()


def _product_payload(index: int) -> str:
    return encode_payload(
        DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id=make_product_id_value(index)),
    )


def _category_payload(index: int) -> str:
    return encode_payload(
        DeepLinkTarget(kind=DeepLinkKind.CATEGORY, id=make_category_id(index)),
    )
