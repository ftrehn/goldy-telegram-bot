"""Which buttons the product card draws, and what each one is hidden by.

Every other screen in the storefront shows the same widgets to everybody; the
card decides. Three flags out of its getter switch four widgets on and off, and
the rule behind them is a commercial one rather than a technical one: a product
with no price for this customer cannot be ordered through the bot, and a
product with nothing on the shelf can — that is what the shop brings in to
order and where its margin is.

Nothing here reads the ``when=`` written in ``dialogs.py``. Each test asks the
widget's own condition what it would do with a screenful of data, so a flag
renamed on one side of the pair fails here rather than at the moment a
customer opens a card and finds no way to buy anything.

The texts these windows hold are rendered in both languages by
``test_wiring``, which walks every dialog rather than this one.
"""

from typing import Final

from aiogram_dialog import Window
from aiogram_dialog.widgets.media import StaticMedia

from goldy.presentation.telegram.common.formatting import NO, YES
from goldy.presentation.telegram.handlers.catalog import CATALOG_DIALOG
from goldy.presentation.telegram.handlers.catalog.callbacks import QUANTITY_ID
from goldy.presentation.telegram.handlers.catalog.states import CatalogStates
from tests.unit.presentation.telegram.widgets import (
    is_shown,
    walk,
    widget_of,
    window_of,
)

ADD_TO_CART_ID: Final[str] = "add_to_cart"
DESCRIPTION_ID: Final[str] = "description"

CARD: Final[Window] = window_of(CATALOG_DIALOG, CatalogStates.CARD)

A_PRICED_PRODUCT: Final[dict[str, object]] = {
    "is_priced": True,
    "has_description": True,
    "has_image": True,
    "in_stock": YES,
    "stock": "12",
}
"""One screenful of card data, with every switch on.

Named flags rather than a rendered card: these four are the whole contract
between ``card_getter`` and the window, and every test below turns exactly one
of them off.
"""


def test_a_product_with_no_price_offers_no_way_to_order_it() -> None:
    """The only thing that ever takes the buy button away.

    A product with no row under this customer's price type cannot be put in a
    cart at all — the cart stores a snapshot of the price, and there is none to
    snapshot. The card says "price on request" and stops there.
    """
    card = {**A_PRICED_PRODUCT, "is_priced": False}

    assert not is_shown(widget_of(CARD, ADD_TO_CART_ID), card)
    assert not is_shown(widget_of(CARD, QUANTITY_ID), card)


def test_nothing_on_the_shelf_leaves_the_buy_button_exactly_where_it_was() -> None:
    """Stock is a projection of 1C with no reservation behind it.

    Hiding the button at zero would block precisely the goods the shop brings
    in to order, so the badge changes wording and the keyboard does not change
    at all. The pair is asserted together because the failure this guards
    against is a well-meant ``when="in_stock"`` added to one of them.
    """
    card = {**A_PRICED_PRODUCT, "in_stock": NO, "stock": "0"}

    assert is_shown(widget_of(CARD, ADD_TO_CART_ID), card)
    assert is_shown(widget_of(CARD, QUANTITY_ID), card)


def test_the_description_button_is_offered_only_when_there_is_a_description() -> None:
    """A button opening an empty screen is worse than no button.

    1C leaves the description empty for most of the catalog, so this is the
    ordinary case rather than the edge one.
    """
    button = widget_of(CARD, DESCRIPTION_ID)

    assert is_shown(button, A_PRICED_PRODUCT)
    assert not is_shown(button, {**A_PRICED_PRODUCT, "has_description": False})


def test_a_product_with_no_picture_is_drawn_without_one() -> None:
    """``StaticMedia`` would otherwise be handed an empty url.

    Telegram refuses the send, so the card does not appear — a product with no
    photo is most of a freshly imported catalog, which makes this the state the
    screen is usually in.
    """
    photo = next(widget for widget in walk(CARD) if isinstance(widget, StaticMedia))

    assert is_shown(photo, A_PRICED_PRODUCT)
    assert not is_shown(photo, {**A_PRICED_PRODUCT, "has_image": False})
