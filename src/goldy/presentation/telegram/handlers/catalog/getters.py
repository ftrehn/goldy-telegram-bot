"""What every storefront screen puts in front of the customer.

Each getter reads through the mediator on the render that needs it, and none
of them keeps a page of the catalog in ``dialog_data``. A listing is one page
out of thousands of products, and a copy held in the dialog would be a copy
that goes stale the moment an import lands — which is the same reason the
paging is server-side.

Two things *are* written into ``dialog_data`` here, and both are a record of
what was drawn rather than a cache of what was read: the names of the
categories on the level currently on screen, and the name of the product whose
card is open. The buttons drawn from them are pressed on that very screen, and
their callbacks have nothing but an id to go on — ``Select`` hands a callback
the item id and nothing else. The alternative is a second query to name a thing
the person is already looking at.

Values that end up inside message text go through
:func:`goldy.presentation.telegram.common.formatting.for_message_text`; values
that end up on a button do not. Its docstring says why, and it says it in one
place because five dialogs make the same decision.
"""

from collections.abc import Mapping
from typing import Any, Final

from aiogram_dialog import DialogManager
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.query_params.catalog_filters import ProductSortField
from goldy.application.common.views.catalog import ProductListItemView, ProductView
from goldy.application.queries.catalog.get_product.query import GetProductQuery
from goldy.application.queries.catalog.list_categories.query import ListCategoriesQuery
from goldy.application.queries.catalog.list_products.query import ListProductsQuery
from goldy.application.queries.catalog.search_products.query import SearchProductsQuery
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import (
    MAX_PLACEABLE_LENGTH,
    MESSAGE_LIMIT,
    flag,
    for_message_text,
    format_price,
    format_stock_amount,
)
from goldy.presentation.telegram.common.paging import (
    page_request,
    paging_data,
)

PRODUCTS_PAGE_KEY: Final[str] = "products_page"
RESULTS_PAGE_KEY: Final[str] = "results_page"
"""Two page counters, because this dialog pages two different lists.

Leaving a category listing on page four and then searching must not open the
results on page four as well — which is exactly what one shared counter would
do, and it would look like the search is broken rather than like the pager is.
"""

CATEGORY_PATH_KEY: Final[str] = "category_path"
LEVEL_NAMES_KEY: Final[str] = "level_names"
PRODUCT_ID_KEY: Final[str] = "product_id"
PRODUCT_NAME_KEY: Final[str] = "product_name"
TERM_KEY: Final[str] = "term"
SORT_KEY: Final[str] = "sort"
ORIGIN_KEY: Final[str] = "origin"

CAPTION_LIMIT: Final[int] = 1024
"""How much text Telegram lets a photo carry.

The card is a photo with a caption, so this is its budget and not the 4096 a
plain message has. Telegram does not trim an over-long caption — it refuses the
whole message, so the screen would simply fail to appear.
"""

ELLIPSIS: Final[str] = "…"
"""Punctuation rather than wording, which is why it is not a Fluent key.

Both languages cut a sentence short the same way, and a key here would mean a
translator maintaining a character.
"""


def category_path(manager: DialogManager) -> list[list[str]]:
    """The groups walked into so far, each as an ``[id, name]`` pair.

    A breadcrumb rather than a single "current category", because going up a
    level has to work without asking the catalog who the parent's parent is.
    Lists rather than tuples: this is stored in Redis as JSON, which has no
    tuples and would hand a list back anyway.
    """
    path: list[list[str]] = manager.dialog_data.setdefault(CATEGORY_PATH_KEY, [])

    return path


def current_category_id(manager: DialogManager) -> str | None:
    """Which group is open, or ``None`` at the top of the catalog."""
    path = category_path(manager)

    return path[-1][0] if path else None


def current_category_name(manager: DialogManager) -> str | None:
    """What the open group is called, as it was labelled when tapped."""
    path = category_path(manager)

    return path[-1][1] if path else None


def current_sort(manager: DialogManager) -> ProductSortField:
    """How the listing is ordered, by name until somebody says otherwise.

    Name first rather than price: a storefront that opens on the cheapest item
    ranks the shop's own catalog for it.
    """
    stored: str = manager.dialog_data.get(SORT_KEY, ProductSortField.NAME.value)

    return ProductSortField(stored)


def current_term(manager: DialogManager) -> str:
    """The last thing the person searched for."""
    term: str = manager.dialog_data.get(TERM_KEY, "")

    return term


def selected_product_id(manager: DialogManager) -> str:
    """Which card is open."""
    product_id: str = manager.dialog_data[PRODUCT_ID_KEY]

    return product_id


def selected_product_name(manager: DialogManager) -> str:
    """The name last drawn on the card, for the toast that confirms an add."""
    name: str = manager.dialog_data.get(PRODUCT_NAME_KEY, "")

    return name


def level_names(manager: DialogManager) -> dict[str, str]:
    """Names of the groups on the level currently on screen, keyed by id."""
    names: dict[str, str] = manager.dialog_data.get(LEVEL_NAMES_KEY, {})

    return names


@inject
async def categories_getter(
    dialog_manager: DialogManager,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """One level of the tree, with the group it hangs under as a heading.

    The heading comes from the query rather than from the breadcrumb, so a
    group renamed in 1C reads correctly the moment the screen is redrawn. The
    breadcrumb is the fallback for the one case the query cannot serve: a group
    deactivated by an import sweep comes back as ``parent=None``, and a heading
    that silently turned into "Catalog" would tell the customer they are
    somewhere they are not.
    """
    view = await sender.send(
        ListCategoriesQuery(parent_id=current_category_id(dialog_manager)),
    )
    dialog_manager.dialog_data[LEVEL_NAMES_KEY] = {
        category.id: category.name for category in view.categories
    }
    fallback = current_category_name(dialog_manager)
    name = view.parent.name if view.parent is not None else fallback

    return {
        "categories": [(category.name, category.id) for category in view.categories],
        "has_categories": view.has_subgroups,
        "is_root": not category_path(dialog_manager),
        "name": for_message_text(name or ""),
    }


@inject
async def products_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """One page of the open group, or of the whole catalog at the top.

    The category selects its whole subtree, which is why standing on a group
    with subgroups still lists products: in 1C the goods sit in the leaves, and
    a listing restricted to the node itself would be empty almost everywhere.
    """
    limit, offset = page_request(dialog_manager, key=PRODUCTS_PAGE_KEY)
    sort_by = current_sort(dialog_manager)
    view = await sender.send(
        ListProductsQuery(
            category_id=current_category_id(dialog_manager),
            limit=limit,
            offset=offset,
            sort_by=sort_by,
        ),
    )
    name = current_category_name(dialog_manager)
    heading = name if name is not None else i18n.get(text_keys.CATALOG_ALL_PRODUCTS)

    return {
        "products": [listing_row(i18n, product) for product in view.products],
        "is_empty": not view.products,
        "category": for_message_text(heading),
        "sort": sort_by.value,
        **paging_data(dialog_manager, total=view.total, key=PRODUCTS_PAGE_KEY),
    }


@inject
async def search_results_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """One page of search results, or the words for having found nothing.

    An empty result is not an error and is not a different screen: the query is
    still on it, so the person can see what was actually searched for and fix a
    typo rather than wonder which of the two words was wrong.
    """
    term = current_term(dialog_manager)
    limit, offset = page_request(dialog_manager, key=RESULTS_PAGE_KEY)
    view = await sender.send(
        SearchProductsQuery(term=term, limit=limit, offset=offset),
    )

    return {
        "products": [listing_row(i18n, product) for product in view.products],
        "is_empty": view.is_empty,
        "term": for_message_text(term),
        **paging_data(dialog_manager, total=view.total, key=RESULTS_PAGE_KEY),
    }


@inject
async def card_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """One product, priced for whoever is looking at it.

    ``has_price`` decides whether the "add to cart" button is drawn at all, and
    it is the only thing that ever hides it. Stock does not: a product at zero
    is one the shop brings in to order, the badge says so, and hiding the
    button there would block exactly the goods the shop makes its margin on.

    The excerpt is cut to whatever the caption has left after the rest of the
    card is rendered, measured rather than guessed. Measuring the rendered text
    counts the HTML tags too, which Telegram does not — so the estimate errs
    towards a shorter excerpt, and a shorter excerpt still fits.
    """
    view = await sender.send(
        GetProductQuery(product_id=selected_product_id(dialog_manager))
    )
    dialog_manager.dialog_data[PRODUCT_NAME_KEY] = view.name
    card = card_arguments(i18n, view)

    return {
        **card,
        "excerpt": card_excerpt(i18n, view.description, card),
        "has_description": view.has_description,
        "has_image": view.image_url is not None,
        "image_url": view.image_url or "",
        "is_priced": view.is_priced,
    }


@inject
async def description_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """The whole description, on a screen with no photo to pay for.

    Read again rather than carried over from the card, for the same reason the
    card is read again every render: a description edited in 1C between two
    screens should be the one the customer reads, and there is no copy to
    invalidate if no copy is kept.

    Two ceilings, and Telegram's is the higher of them. The description reaches
    this screen as a single Fluent argument, and Fluent refuses a placeable over
    ``MAX_PLACEABLE_LENGTH`` by failing the whole message rather than by cutting
    it — so a description of three thousand characters, which is exactly the
    kind this screen exists for, would leave the customer with nothing at all
    where the message limit alone would have let it through.
    """
    view = await sender.send(
        GetProductQuery(product_id=selected_product_id(dialog_manager))
    )
    name = for_message_text(view.name)

    return {
        "name": name,
        "description": shorten(
            for_message_text(view.description or ""),
            description_budget(i18n, name),
        ),
    }


def description_budget(i18n: I18nContext, name: str) -> int:
    """How much description this screen can carry, under the lower of two caps.

    A pure function for the reason :func:`card_arguments` is one: the cap that
    actually binds is not Telegram's and is therefore the one nobody would
    think to assert against a running dialog.
    """
    skeleton = i18n.get(text_keys.CATALOG_DESCRIPTION, name=name, description="")

    return min(MESSAGE_LIMIT - len(skeleton), MAX_PLACEABLE_LENGTH)


def card_arguments(i18n: I18nContext, view: ProductView) -> dict[str, str]:
    """Everything ``catalog-card`` and the two messages inside it ask for.

    Eight values for what looks like four, because the card embeds
    ``catalog-sku`` and ``stock-badge``, and a referenced Fluent message is
    rendered in the caller's scope: it has no arguments of its own and reads
    the ones passed here. One of them missing is not a placeholder left in the
    text — ``FluentRuntimeCore`` raises, and the screen does not render at all.

    A pure function rather than lines inside the getter so that exactly this
    can be asserted without a dialog, a container or a database.

    ``has_price`` is passed although today's wording does not read it. The
    price line has no branch for a product with no price, so it currently says
    "Price: price on request per pc"; sending the flag now means the wording
    can grow that branch without every card breaking on a missing argument in
    between.
    """
    return {
        "name": for_message_text(view.name),
        "price": format_price(i18n, view.unit_price),
        "has_price": flag(value=view.is_priced),
        "unit": for_message_text(view.unit_name),
        "has_sku": flag(value=view.sku is not None),
        "sku": for_message_text(view.sku or ""),
        "in_stock": flag(value=view.is_in_stock),
        "stock": format_stock_amount(view.stock),
    }


def card_excerpt(
    i18n: I18nContext,
    description: str | None,
    card: Mapping[str, str],
) -> str:
    """As much of the description as the caption has room for.

    The room is measured by rendering the card without an excerpt rather than
    guessed at with a round number: the rest of the caption is a name, a price
    and a badge, all of which vary. Measuring the rendered text counts the HTML
    tags, which Telegram does not count towards the limit — so the estimate
    errs short, and short still fits.
    """
    skeleton = i18n.get(text_keys.CATALOG_CARD, excerpt="", **card)

    return shorten(
        for_message_text(description or ""),
        CAPTION_LIMIT - len(skeleton),
    )


def listing_row(i18n: I18nContext, product: ProductListItemView) -> tuple[str, str]:
    """One row of a listing: the label to draw and the id behind it.

    Not escaped, unlike everything that goes into message text: this becomes a
    button label, which Telegram takes as plain text — escaping it would show
    the customer the escape sequence.
    """
    label = i18n.get(
        text_keys.CATALOG_LIST_ITEM,
        name=product.name,
        price=format_price(i18n, product.unit_price),
    )

    return label, product.id


def shorten(text: str, limit: int) -> str:
    """Cuts text to fit, on a word boundary where there is one."""
    if limit <= 0:
        return ""

    if len(text) <= limit:
        return text

    cut = text[: limit - len(ELLIPSIS)]
    head, separator, _ = cut.rpartition(" ")

    return f"{head if separator else cut}{ELLIPSIS}"
