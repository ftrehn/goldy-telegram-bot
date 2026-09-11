"""The seven screens of the storefront.

The card is a photo with a caption, which is where the 1024-character budget in
the card getter comes from, and why the full description is a screen of its own
rather than more text under the picture.

Quantity is picked with a counter on the card, one step at a time, and there is
deliberately no typed input on that screen: in an open catalog typed text is a
search, and a screen where the same keystrokes mean two different things is a
screen that guesses. Somebody ordering five hundred of something sets the
number on the cart line, where typing a quantity is unambiguous.

"Nothing found" is this window rendered without a list rather than a state of
its own. Whether a search matched is known only after the query the getter
runs, and a getter that switched states would re-enter the render it is in the
middle of.

The card offers the cart as a plain ``Start`` rather than ``RESET_STACK``:
somebody who has just added something and wants to look at what they have is
one "back" away from changing their mind, and that back has to land on the card
they were reading. The import is of the cart's ``states`` module and not of its
package, because the cart's own windows link back here — through a package
``__init__`` that pulls in ``dialogs``, the two would meet each other half
built. A ``states`` module imports nothing local and is safe from either side.
"""

import operator
from typing import Final

from aiogram import F
from aiogram.enums import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Counter,
    Group,
    Row,
    Select,
    Start,
    SwitchTo,
)
from aiogram_dialog.widgets.media import StaticMedia
from aiogram_dialog.widgets.text import Format

from goldy.domain.common.values.quantity import MAX_QUANTITY
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.paging import paging_row
from goldy.presentation.telegram.common.widgets import I18NFormat
from goldy.presentation.telegram.handlers.cart.states import CartStates
from goldy.presentation.telegram.handlers.catalog.callbacks import (
    DEFAULT_QUANTITY,
    QUANTITY_ID,
    on_add_to_cart,
    on_card_back,
    on_category_selected,
    on_category_up,
    on_close,
    on_dialog_start,
    on_product_selected,
    on_result_selected,
    on_search_typed,
    on_show_products,
    on_sort_toggled,
)
from goldy.presentation.telegram.handlers.catalog.getters import (
    PRODUCTS_PAGE_KEY,
    RESULTS_PAGE_KEY,
    card_getter,
    categories_getter,
    description_getter,
    products_getter,
    search_results_getter,
)
from goldy.presentation.telegram.handlers.catalog.states import CatalogStates

CATALOG_DIALOG: Final[Dialog] = Dialog(
    Window(
        I18NFormat(text_keys.CATALOG_TITLE, when="is_root"),
        I18NFormat(
            text_keys.CATALOG_CATEGORY_TITLE,
            name=Format("{name}"),
            when=~F["is_root"],
        ),
        I18NFormat(text_keys.CATALOG_PICK_CATEGORY, when="has_categories"),
        I18NFormat(text_keys.CATALOG_NO_CATEGORIES, when=~F["has_categories"]),
        Group(
            Select(
                Format("{item[0]}"),
                id="category_select",
                item_id_getter=operator.itemgetter(1),
                items="categories",
                on_click=on_category_selected,
            ),
            width=1,
        ),
        Row(
            SwitchTo(
                I18NFormat(text_keys.CATALOG_SHOW_PRODUCTS_BUTTON),
                id="show_products",
                state=CatalogStates.PRODUCTS,
                on_click=on_show_products,
            ),
            SwitchTo(
                I18NFormat(text_keys.CATALOG_SEARCH_BUTTON),
                id="search",
                state=CatalogStates.SEARCH,
            ),
        ),
        Button(
            I18NFormat(text_keys.CATALOG_UP_BUTTON),
            id="category_up",
            on_click=on_category_up,
            when=~F["is_root"],
        ),
        Button(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close", on_click=on_close),
        MessageInput(on_search_typed, content_types=[ContentType.TEXT]),
        state=CatalogStates.CATEGORIES,
        getter=categories_getter,
    ),
    Window(
        I18NFormat(
            text_keys.CATALOG_LIST_TITLE,
            category=Format("{category}"),
            page=Format("{page}"),
            pages=Format("{pages}"),
            total=Format("{total}"),
        ),
        I18NFormat(text_keys.CATALOG_LIST_EMPTY, when="is_empty"),
        Group(
            Select(
                Format("{item[0]}"),
                id="product_select",
                item_id_getter=operator.itemgetter(1),
                items="products",
                on_click=on_product_selected,
            ),
            width=1,
        ),
        paging_row(key=PRODUCTS_PAGE_KEY, id_prefix="products"),
        Row(
            Button(
                I18NFormat(text_keys.CATALOG_SORT_BUTTON, sort=Format("{sort}")),
                id="sort",
                on_click=on_sort_toggled,
            ),
            SwitchTo(
                I18NFormat(text_keys.CATALOG_SEARCH_BUTTON),
                id="search",
                state=CatalogStates.SEARCH,
            ),
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=CatalogStates.CATEGORIES,
        ),
        MessageInput(on_search_typed, content_types=[ContentType.TEXT]),
        state=CatalogStates.PRODUCTS,
        getter=products_getter,
    ),
    Window(
        StaticMedia(url=Format("{image_url}"), when="has_image"),
        I18NFormat(
            text_keys.CATALOG_CARD,
            name=Format("{name}"),
            price=Format("{price}"),
            has_price=Format("{has_price}"),
            unit=Format("{unit}"),
            has_sku=Format("{has_sku}"),
            sku=Format("{sku}"),
            in_stock=Format("{in_stock}"),
            stock=Format("{stock}"),
            excerpt=Format("{excerpt}"),
        ),
        Counter(
            id=QUANTITY_ID,
            plus=I18NFormat(text_keys.CART_PLUS_BUTTON),
            minus=I18NFormat(text_keys.CART_MINUS_BUTTON),
            min_value=DEFAULT_QUANTITY,
            max_value=MAX_QUANTITY,
            default=DEFAULT_QUANTITY,
            when="is_priced",
        ),
        Button(
            I18NFormat(text_keys.CATALOG_ADD_BUTTON),
            id="add_to_cart",
            on_click=on_add_to_cart,
            when="is_priced",
        ),
        Row(
            SwitchTo(
                I18NFormat(text_keys.CATALOG_DESCRIPTION_BUTTON),
                id="description",
                state=CatalogStates.DESCRIPTION,
                when="has_description",
            ),
            Start(
                I18NFormat(text_keys.CATALOG_OPEN_CART_BUTTON),
                id="open_cart",
                state=CartStates.MAIN,
            ),
        ),
        Button(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="card_back",
            on_click=on_card_back,
        ),
        state=CatalogStates.CARD,
        getter=card_getter,
    ),
    Window(
        I18NFormat(
            text_keys.CATALOG_DESCRIPTION,
            name=Format("{name}"),
            description=Format("{description}"),
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=CatalogStates.CARD,
        ),
        state=CatalogStates.DESCRIPTION,
        getter=description_getter,
    ),
    Window(
        I18NFormat(text_keys.CATALOG_SEARCH_PROMPT),
        MessageInput(on_search_typed, content_types=[ContentType.TEXT]),
        SwitchTo(
            I18NFormat(text_keys.CATALOG_TO_CATALOG_BUTTON),
            id="to_catalog",
            state=CatalogStates.CATEGORIES,
        ),
        state=CatalogStates.SEARCH,
    ),
    Window(
        I18NFormat(
            text_keys.CATALOG_SEARCH_TITLE,
            term=Format("{term}"),
            total=Format("{total}"),
            page=Format("{page}"),
            pages=Format("{pages}"),
            when=~F["is_empty"],
        ),
        I18NFormat(
            text_keys.CATALOG_SEARCH_EMPTY,
            term=Format("{term}"),
            when="is_empty",
        ),
        Group(
            Select(
                Format("{item[0]}"),
                id="result_select",
                item_id_getter=operator.itemgetter(1),
                items="products",
                on_click=on_result_selected,
            ),
            width=1,
        ),
        paging_row(key=RESULTS_PAGE_KEY, id_prefix="results"),
        Row(
            SwitchTo(
                I18NFormat(text_keys.CATALOG_SEARCH_AGAIN_BUTTON),
                id="search_again",
                state=CatalogStates.SEARCH,
            ),
            SwitchTo(
                I18NFormat(text_keys.CATALOG_TO_CATALOG_BUTTON),
                id="to_catalog",
                state=CatalogStates.CATEGORIES,
            ),
        ),
        MessageInput(on_search_typed, content_types=[ContentType.TEXT]),
        state=CatalogStates.RESULTS,
        getter=search_results_getter,
    ),
    on_start=on_dialog_start,
)
