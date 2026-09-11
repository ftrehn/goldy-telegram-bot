"""Whether the five storefront commands reach a screen, and who they let in.

The dialogs themselves are covered by their own unit tests, which render the
messages and exercise the pure parts of the getters. What none of that can say
is whether a command reaches anything at all: a dialog left out of ``DIALOGS``,
a router attached below the catch-all, or a state group nobody registered all
produce code that imports, type-checks and answers "unknown command".

These tests feed a real update into the real dispatcher, so the answer comes
from the assembly rather than from the tuples. The catalog is empty here on
purpose — an empty shop still has to draw its screens, and a storefront that
only works once 1C has imported something is a storefront nobody can smoke-test
before the first import.
"""

import pytest
from aiogram.methods import SendMessage

from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.ports.catalog import CatalogSnapshot
from goldy.domain.users.values.user_role import UserRole
from goldy.presentation.telegram.common import text_keys
from tests.integration.arrange import CommandSender
from tests.integration.telegram.arrange import (
    PersonRegistrar,
    TextRenderer,
    UpdateFeeder,
)
from tests.integration.telegram.personas import a_stranger
from tests.integration.telegram.sent import SentCalls
from tests.unit.factories.catalog_factories import (
    make_price_row,
    make_price_type_row,
    make_product_row,
    make_snapshot,
    make_stock_row,
)

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

STOREFRONT_COMMANDS = ("/catalog", "/search", "/cart", "/orders")


@pytest.mark.parametrize("command", STOREFRONT_COMMANDS)
async def test_a_stranger_reaches_none_of_the_storefront(
    command: str,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """Fail-closed, and fail-closed for screens written after the gate was.

    ``AuthMiddleware`` is an outer middleware on ``dp.update``, so it runs
    before any router is consulted — which is exactly why a storefront added
    months later is covered without anybody remembering to cover it. ``only``
    is the assertion: one refusal, not a refusal followed by a catalog window.
    """
    await feed(a_stranger().says(command))

    assert sent.only(SendMessage).text == text(text_keys.AUTH_REGISTRATION_REQUIRED)


async def test_a_stranger_is_turned_away_from_the_staff_queue_as_well(
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """And is told to register rather than told the command does not exist.

    The gate answers before the staff filter is ever reached, so a stranger
    learns nothing about the command either way — what they are told is what
    everyone unregistered is told about everything.
    """
    await feed(a_stranger().says("/manage_orders"))

    assert sent.only(SendMessage).text == text(text_keys.AUTH_REGISTRATION_REQUIRED)


async def test_the_catalog_opens_on_a_shop_with_nothing_in_it(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """The first screen of the shop, drawn before 1C has imported anything.

    An empty catalog is the state every deployment starts in, and a storefront
    whose first screen only renders after an import is one nobody can check
    until it is too late to check it.
    """
    person = await register_person()

    await feed(person.says("/catalog"))

    assert text(text_keys.CATALOG_TITLE) in sent.last_text()
    assert text(text_keys.CATALOG_NO_CATEGORIES) in sent.last_text()


async def test_search_without_a_term_asks_for_one(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """``/search`` on its own is an invitation, not a refusal.

    The other two ways in — a term after the command, and text typed into an
    open catalog window — both need a catalog with something in it. This one
    does not, which makes it the one that belongs in a smoke test.
    """
    person = await register_person()

    await feed(person.says("/search"))

    assert sent.last_text() == text(text_keys.CATALOG_SEARCH_PROMPT)


async def test_the_cart_opens_empty_rather_than_refusing(
    register_person: PersonRegistrar,
    send_worker_command: CommandSender,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """A person who has never added anything has no cart row at all.

    ``GetCartQuery`` answers with an empty view rather than "no cart", and this
    is the test that says so end to end: the alternative would greet every new
    customer's first ``/cart`` with an error.

    A price list is imported first, and that is not scene-setting. The cart
    screen resolves the price list of whoever is looking at it before it has
    anything to draw, and ``PriceTypeProvider`` treats a shop with no price
    types at all as a broken import rather than as an empty one — deliberately,
    because that is what it is. So the empty *cart* is only reachable in a shop
    that has been imported into at least once.
    """
    person = await register_person()
    await send_worker_command(ImportCatalogCommand(snapshot=_a_shop()))

    await feed(person.says("/cart"))

    assert sent.last_text() == text(text_keys.CART_SCREEN_EMPTY)


async def test_the_order_history_opens_empty_too(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    person = await register_person()

    await feed(person.says("/orders"))

    assert text(text_keys.ORDERS_EMPTY) in sent.last_text()


async def test_a_customer_is_never_told_the_order_queue_exists(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """The staff filter sits on the router, so this falls through to the fallback.

    "Unknown command" and not "forbidden", because a refusal confirms that the
    command is real. It is the same reason the command is kept out of the
    published menu — one half of the rule without the other is no rule.
    """
    person = await register_person()

    await feed(person.says("/manage_orders"))

    assert sent.only(SendMessage).text == text(text_keys.UNKNOWN_COMMAND)


async def test_staff_reach_the_order_queue(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    person = await register_person(role=UserRole.MANAGER)

    await feed(person.says("/manage_orders"))

    assert text(text_keys.MANAGE_ORDERS_EMPTY) in sent.last_text()


async def test_a_command_typed_inside_the_catalog_is_not_read_as_a_search(
    register_person: PersonRegistrar,
    send_worker_command: CommandSender,
    feed: UpdateFeeder,
    sent: SentCalls,
    text: TextRenderer,
) -> None:
    """The one thing the router order exists for, checked by doing it.

    Three catalog windows carry a ``MessageInput`` that treats any typed text
    as a search term. Attached above the feature routers they would take
    ``/cart`` as a search for the word "/cart" — and it is precisely somebody
    halfway through browsing who types ``/cart``. Nothing in the tuples says
    this; only feeding the update does.
    """
    person = await register_person()
    await send_worker_command(ImportCatalogCommand(snapshot=_a_shop()))
    await feed(person.says("/catalog"))
    sent.forget()

    await feed(person.says("/cart"))

    assert sent.last_text() == text(text_keys.CART_SCREEN_EMPTY)


async def test_the_storefront_stays_quiet_in_a_group(
    register_person: PersonRegistrar,
    feed: UpdateFeeder,
    sent: SentCalls,
) -> None:
    """Every storefront router carries the private-chat filter, and must.

    An order is somebody's address and telephone number. A ``/cart`` that
    answered in a group would put the contents of one person's basket in front
    of everybody in it.
    """
    person = await register_person()

    await feed(person.says_in_a_group("/cart"))

    assert sent.all(SendMessage) == ()


def _a_shop() -> CatalogSnapshot:
    """The smallest shop that is a shop: one product, priced, with stock.

    Small on purpose. What these tests are about is whether a command reaches a
    screen, so the catalog only has to be non-empty — the contents of the
    projection are the business of the persistence tests, which check them
    against SQL rather than against a rendered message.
    """
    return make_snapshot(
        products=(make_product_row(1),),
        price_types=(make_price_type_row(),),
        prices=(make_price_row(1),),
        stock=(make_stock_row(1),),
    )
