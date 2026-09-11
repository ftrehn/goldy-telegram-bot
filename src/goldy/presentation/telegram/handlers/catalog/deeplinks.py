"""Where a link from the website lands in the storefront, and what if it cannot.

One function with one job: turn the target a payload named into the screen that
should open. It is separate from the ``/start`` handler because the decision is
about the catalog — which window, with what in it, and which sentence goes in
front of it — and separate from the dialog because the decision has to be made
*before* a window is drawn.

That ordering is the same one ``/search 40-1234`` already relies on. A getter
runs in the middle of a render and cannot switch states, so a card that
discovered in its own getter that the product is gone would have nowhere to go;
resolving first costs one read on a path that was going to read the product
anyway, and buys a screen that is right the first time it appears.

A link that leads nowhere never becomes a refusal. The visitor arrived from a
page on the shop's own website, and the worst available outcome is a bot that
looks broken, so every failure here ends the same way: one sentence, and the
catalog from the top.
"""

from dataclasses import dataclass, field
from typing import Final

from aiogram.fsm.state import State

from goldy.application.common.mediator.sender import Sender
from goldy.application.error import ProductNotFoundError
from goldy.application.queries.catalog.get_product.query import GetProductQuery
from goldy.application.queries.catalog.list_categories.query import ListCategoriesQuery
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.deeplinks import DeepLinkKind, DeepLinkTarget
from goldy.presentation.telegram.handlers.catalog.getters import PRODUCT_ID_KEY
from goldy.presentation.telegram.handlers.catalog.states import CatalogStates

CATEGORY_ID_KEY: Final[str] = "category_id"
CATEGORY_NAME_KEY: Final[str] = "category_name"
"""Two keys that live in a dialog's *start* data and nowhere else.

The storefront keeps the group it is standing in on a breadcrumb in
``dialog_data``, built one tap at a time. A link arrives with no taps behind
it, so the first crumb is handed over at start instead — id and name together,
because the categories screen falls back to the breadcrumb whenever the query
cannot supply a heading, and a crumb with no name renders a blank title.
"""


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Which storefront screen to open, with what, and what to say first.

    A value rather than a pair of side effects, so that "a withdrawn product
    sends you to the catalog with an apology" is a fact a test can read off a
    return value — no dialog manager, no bot, no Telegram.
    """

    state: State
    data: dict[str, str] = field(default_factory=dict)
    notice: str | None = None


async def resolve_deeplink(
    sender: Sender,
    target: DeepLinkTarget | None,
) -> CatalogEntry:
    """Decides where a link lands, having checked that it still leads anywhere.

    ``None`` means the payload did not parse — it was truncated by whatever
    copied it, it was forged, or it names a kind of thing a later version of
    this bot will understand and this one does not. All three are answered like
    a product that is gone, for the reason ``DEEPLINK_PRODUCT_GONE`` gives: an
    unreadable payload names nothing, so there is nothing more specific that
    would also be true.
    """
    if target is None:
        return _gone(text_keys.DEEPLINK_PRODUCT_GONE)

    if target.kind is DeepLinkKind.PRODUCT:
        return await _product_entry(sender, target.id)

    return await _category_entry(sender, target.id)


async def _product_entry(sender: Sender, product_id: str) -> CatalogEntry:
    """The card, unless the shop has stopped offering that product.

    Two ways for it to be gone, and the second is the one that would otherwise
    slip through. An import sweep deletes nothing — it deactivates, because
    placed orders point at the row — so a withdrawn product is still perfectly
    readable and only ``is_active`` says otherwise; the card getter never looks
    at that flag because every other way to reach a card goes through a listing
    that has already filtered on it. A link has no listing in front of it.

    A product that never existed, which is also what a forged payload looks
    like, arrives as ``ProductNotFoundError`` instead. Nothing else raised by
    this read is caught: a price type that is not configured, or one in a
    currency this service does not know, is a fault of ours and belongs in the
    hands of the error handler that has words for it.
    """
    try:
        view = await sender.send(GetProductQuery(product_id=product_id))
    except ProductNotFoundError:
        return _gone(text_keys.DEEPLINK_PRODUCT_GONE)

    if not view.is_active:
        return _gone(text_keys.DEEPLINK_PRODUCT_GONE)

    return CatalogEntry(state=CatalogStates.CARD, data={PRODUCT_ID_KEY: view.id})


async def _category_entry(sender: Sender, category_id: str) -> CatalogEntry:
    """The group's own screen, with the crumb that lets "up" work from it.

    ``ListCategoriesQuery`` answers with the level *and* the node it hangs
    under, and here the node is the whole point: the read side refuses an
    inactive category and returns its subgroups regardless, so a swept group
    would render as an ordinary screen with a missing heading. ``parent is
    None`` is the only sign, and it is unambiguous because a link always names
    a group — only the top of the catalog has no parent, and no link points
    there.
    """
    view = await sender.send(ListCategoriesQuery(parent_id=category_id))

    if view.parent is None:
        return _gone(text_keys.DEEPLINK_CATEGORY_GONE)

    return CatalogEntry(
        state=CatalogStates.CATEGORIES,
        data={CATEGORY_ID_KEY: view.parent.id, CATEGORY_NAME_KEY: view.parent.name},
    )


def _gone(notice: str) -> CatalogEntry:
    """The catalog from the top, with a sentence explaining why you are there."""
    return CatalogEntry(state=CatalogStates.CATEGORIES, notice=notice)
