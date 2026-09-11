"""What the storefront does when a button is pressed or a word is typed.

Nothing here catches a domain error. A term of one character, a product swept
out of the catalog between the listing and the tap, a quantity over the
ceiling — each comes back as its own refusal and is rendered by the one error
handler, which is where the wording for all of them already lives.
"""

from collections.abc import Mapping
from typing import Any, Final

from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.api.entities import Data
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, ManagedCounter, Select
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.query_params.catalog_filters import ProductSortField
from goldy.application.queries.catalog.search_products.query import SearchProductsQuery
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.paging import reset_paging
from goldy.presentation.telegram.common.widgets import I18N_CONTEXT_KEY
from goldy.presentation.telegram.handlers.catalog.deeplinks import (
    CATEGORY_ID_KEY,
    CATEGORY_NAME_KEY,
)
from goldy.presentation.telegram.handlers.catalog.getters import (
    ORIGIN_KEY,
    PRODUCTS_PAGE_KEY,
    PRODUCT_ID_KEY,
    RESULTS_PAGE_KEY,
    SORT_KEY,
    TERM_KEY,
    category_path,
    current_sort,
    level_names,
    selected_product_name,
)
from goldy.presentation.telegram.handlers.catalog.states import CatalogStates

QUANTITY_ID: Final[str] = "catalog_quantity"
DEFAULT_QUANTITY: Final[int] = 1

PRODUCTS_ORIGIN: Final[str] = "products"
RESULTS_ORIGIN: Final[str] = "results"

ORIGIN_STATES: Final[Mapping[str, State]] = {
    PRODUCTS_ORIGIN: CatalogStates.PRODUCTS,
    RESULTS_ORIGIN: CatalogStates.RESULTS,
}
"""Where "back" from a card goes, keyed by where the card was opened from.

A word of our own rather than the state name aiogram gives out: this is written
into ``dialog_data``, which is stored as JSON, and a renamed state would turn
every card opened before the deploy into a dead button.
"""


async def on_dialog_start(start_data: Data, manager: DialogManager) -> None:
    """Takes over what the caller already worked out before opening the dialog.

    Two callers arrive this way. ``/search 40-1234`` resolves the article
    before the first screen is drawn, so the dialog may open straight on a
    card; the term travels with it, so "back" from that card lands on the
    results for what was typed rather than at the top of the catalog. A deep
    link off the shop's website opens either a card with no term behind it at
    all, or the tree standing inside the group it named.

    The origin is written only when both a card and a term arrived, and that
    condition is the whole of the deep link's effect on this function. Set on
    the card alone, "back" from a card opened by a link would switch to the
    results screen for the empty search — which the application layer refuses
    as too short a term, so the only button on that screen would answer with an
    error. With no origin the card falls back to the categories screen, which
    is where somebody who arrived from outside wants to go anyway.
    """
    if not isinstance(start_data, dict):
        return

    for key in (TERM_KEY, PRODUCT_ID_KEY):
        value = start_data.get(key)

        if value is not None:
            manager.dialog_data[key] = value

    if (
        start_data.get(TERM_KEY) is not None
        and start_data.get(PRODUCT_ID_KEY) is not None
    ):
        manager.dialog_data[ORIGIN_KEY] = RESULTS_ORIGIN

    _stand_in_category(start_data, manager)


def _stand_in_category(start_data: Mapping[str, str], manager: DialogManager) -> None:
    """Puts the group a deep link named on the breadcrumb, as if it were tapped.

    The name comes along with the id rather than being looked up, for the same
    reason :func:`on_category_selected` takes it off the screen the button was
    drawn on: the breadcrumb is what the categories screen falls back to when
    the query cannot supply a heading, and a crumb with no name renders a blank
    title. Falling back to the id keeps the screen rendering if a link is ever
    built without one.
    """
    category_id = start_data.get(CATEGORY_ID_KEY)

    if category_id is None:
        return

    category_path(manager).append(
        [category_id, start_data.get(CATEGORY_NAME_KEY, category_id)],
    )


async def on_category_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
) -> None:
    """Walks one level down, remembering what the group was called.

    The name comes off the screen the button was drawn on, because a ``Select``
    hands its callback an id and nothing else, and the listing underneath needs
    a heading. Falling back to the id keeps the screen rendering if the level
    was drawn before a restart.
    """
    path = category_path(manager)
    path.append([item_id, level_names(manager).get(item_id, item_id)])
    reset_paging(manager, key=PRODUCTS_PAGE_KEY)


async def on_category_up(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    """Goes back up one group, to the top of the catalog at the last step."""
    path = category_path(manager)

    if path:
        path.pop()

    reset_paging(manager, key=PRODUCTS_PAGE_KEY)


async def on_show_products(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    """Opens the listing of the group on screen, always at its first page."""
    reset_paging(manager, key=PRODUCTS_PAGE_KEY)


async def on_sort_toggled(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    """Flips the listing between name and price.

    Back to the first page, because page four of one ordering has nothing to do
    with page four of the other — the same button would otherwise look like it
    had scattered the catalog.
    """
    current = current_sort(manager)
    flipped = (
        ProductSortField.PRICE
        if current is ProductSortField.NAME
        else ProductSortField.NAME
    )
    manager.dialog_data[SORT_KEY] = flipped.value
    reset_paging(manager, key=PRODUCTS_PAGE_KEY)


async def on_product_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
) -> None:
    await _open_card(manager, product_id=item_id, origin=PRODUCTS_ORIGIN)


async def on_result_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
) -> None:
    await _open_card(manager, product_id=item_id, origin=RESULTS_ORIGIN)


async def on_card_back(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    """Returns to the list the card was opened from.

    The categories screen is the fallback rather than an error: a card reached
    from neither listing — the article shortcut, before its term was stored —
    still has somewhere sensible to go.
    """
    origin: str = manager.dialog_data.get(ORIGIN_KEY, "")

    await manager.switch_to(ORIGIN_STATES.get(origin, CatalogStates.CATEGORIES))


@inject
async def on_add_to_cart(
    callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Puts the chosen number of this product in the cart and says so.

    The confirmation is a toast on the card rather than a new screen: the
    person is looking at the product they just added, and a screen change would
    take it away from them mid-decision. It is answered on the callback and not
    written into the message behind it — that message may be inaccessible, and
    the toast lands where the finger is anyway.

    Adding accumulates, so a double tap reads as two on the cart screen and is
    undone by the button next to it. Nothing here guards against that on
    purpose: a nonce in every button's payload would be a permanent cost
    against a slip that costs one tap to fix.
    """
    i18n: I18nContext = manager.middleware_data[I18N_CONTEXT_KEY]
    product_id: str = manager.dialog_data[PRODUCT_ID_KEY]

    await sender.send(
        AddToCartCommand(product_id=product_id, quantity=selected_quantity(manager)),
    )
    await reset_quantity(manager)
    await callback.answer(
        i18n.get(text_keys.CATALOG_ADDED_TOAST, name=selected_product_name(manager)),
    )


@inject
async def on_search_typed(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Treats anything typed in an open catalog as a search.

    Safe to claim the text because the feature routers are attached ahead of
    the dialogs: ``/cart`` typed in the middle of the catalog is taken by the
    cart's router, and only what no command claimed reaches here. The
    alternative is answering "I do not understand" to somebody who typed the
    name of a product into a shop.

    Too short a term is refused by the application layer and rendered by the
    error handler, so there is nothing to check here.
    """
    term = (message.text or "").strip()
    manager.dialog_data[TERM_KEY] = term
    reset_paging(manager, key=RESULTS_PAGE_KEY)

    product_id = await exact_match_product_id(sender, term)

    if product_id is None:
        await manager.switch_to(CatalogStates.RESULTS)
        return

    await _open_card(manager, product_id=product_id, origin=RESULTS_ORIGIN)


async def on_close(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    await manager.done()


async def exact_match_product_id(sender: Sender, term: str) -> str | None:
    """Whether this term is an article, and whose.

    Answered by the projection rather than by a guess at the 1C format: the
    read model sets this only when the normalised term matched the article of
    exactly one product, which is the single case where opening a card instead
    of a list cannot be wrong. Any other count — none, two, a hundred — is a
    list.

    One row is asked for, not a page: this decides which screen to open, and
    the screen that opens fetches what it draws.
    """
    view = await sender.send(SearchProductsQuery(term=term, limit=1, offset=0))

    return view.exact_sku_product_id


def selected_quantity(manager: DialogManager) -> int:
    """How many the counter is standing at.

    Whole pieces, because that is what ``Quantity`` allows; the counter itself
    is bounded by the same ceiling, so the cast cannot round anything away.
    """
    counter: ManagedCounter | None = manager.find(QUANTITY_ID)

    if counter is None:
        return DEFAULT_QUANTITY

    return int(counter.get_value())


async def reset_quantity(manager: DialogManager) -> None:
    """Puts the counter back to one.

    Counter values live in the dialog's widget data rather than on a product,
    so without this the three somebody picked for a fitting would follow them
    to the next card and be added silently.
    """
    counter: ManagedCounter | None = manager.find(QUANTITY_ID)

    if counter is not None:
        await counter.set_value(DEFAULT_QUANTITY)


async def _open_card(
    manager: DialogManager,
    *,
    product_id: str,
    origin: str,
) -> None:
    manager.dialog_data[PRODUCT_ID_KEY] = product_id
    manager.dialog_data[ORIGIN_KEY] = origin

    await reset_quantity(manager)
    await manager.switch_to(CatalogStates.CARD)
