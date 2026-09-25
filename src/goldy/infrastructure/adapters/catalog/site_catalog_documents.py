"""The site's catalog JSON, read into rows of our snapshot contract.

The shapes below are the site's (its ``docs/API.md``, ``/catalog/*``), named
in its words; the functions turn them into :class:`CategoryRow`,
:class:`ProductRow`, :class:`PriceRow` and :class:`StockRow`, which are ours.
Every renaming and every substitution the contract leaves to the client is
made here and nowhere else:

- a row's key is the site's ``id`` — the ``XML_ID``, a 1C GUID for items the
  1C exchange manages and ``goldy_*`` for items the site keeps on its own. The
  site's numeric ``site_id`` is not a key: the site says it may change.
- ``sku`` is mandatory on our side and optional on the site's. A missing one
  becomes the ``site_id`` spelled as text, which is what the site's manager
  sees in the admin and can read out on the phone.
- stock arrives as a status. ``in_stock`` and ``out_of_stock`` become a stock
  row with the free quantity (zero for the latter); ``untracked`` — "made to
  order", nobody counts it — becomes **no** stock row, which is exactly how
  the storefront already renders a product it has no stock figure for.
- ``images[0]`` is the product's picture; the others have no place to go yet.

Sections and price types are read strictly: one bad entry refuses the pass,
because the category tree is placed from the whole list and a price list is
what every price hangs on. Items are read one by one, and an item that cannot
become a row is skipped and logged instead — one broken card among thousands
must not stop the other thousands from updating. A skipped item is swept at
finalisation like any item the site stopped sending, which is the honest
outcome: the bot must not keep selling what it cannot read.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from adaptix import Retort, loader
from adaptix.load_error import LoadError, ValueLoadError

from goldy.application.common.ports.catalog import (
    CategoryRow,
    PriceRow,
    PriceTypeRow,
    ProductRow,
    StockRow,
)
from goldy.infrastructure.adapters.catalog.adaptix_support import (
    decimal_through_text,
    load_error_reasons,
)
from goldy.infrastructure.errors import CatalogSourceReadError

logger: Final[logging.Logger] = logging.getLogger(__name__)

STOCK_WAREHOUSE_ID: Final[str] = "*"
"""The site reports one free quantity, not a breakdown by warehouse."""

MAX_ID_LENGTH: Final[int] = 128
MAX_SKU_LENGTH: Final[int] = 64
MAX_NAME_LENGTH: Final[int] = 255
MAX_UNIT_NAME_LENGTH: Final[int] = 32
"""The widths of the projection's columns; a longer value fails the insert."""

COUNTED_STOCK_STATUSES: Final[frozenset[str]] = frozenset({"in_stock", "out_of_stock"})
UNTRACKED_STOCK_STATUS: Final[str] = "untracked"


def _text(value: object) -> str:
    """Any string, blank included — blankness is judged field by field below."""
    if not isinstance(value, str):
        msg = "Expected a string."
        raise ValueLoadError(msg, value)
    return value


_retort: Final[Retort] = Retort(
    recipe=[
        loader(Decimal, decimal_through_text),
        loader(str, _text),
    ],
)


@dataclass(frozen=True, kw_only=True)
class SiteSection:
    """One entry of ``GET /catalog/sections``."""

    id: str
    parent_id: str | None = None
    name: str


@dataclass(frozen=True, kw_only=True)
class SitePriceType:
    """One entry of ``GET /catalog/price-types``."""

    id: str
    name: str
    currency: str


@dataclass(frozen=True, kw_only=True)
class SiteUnit:
    """``unit`` of an item: the OKEI code and the name shown beside a quantity."""

    code: str | None = None
    name: str


@dataclass(frozen=True, kw_only=True)
class SitePrice:
    """``price`` of an item — the retail price, the same for every guest."""

    price_type_id: str
    amount: Decimal
    currency: str


@dataclass(frozen=True, kw_only=True)
class SiteStock:
    """``stock`` of an item. ``status`` is text so a new status is not fatal."""

    status: str
    quantity: Decimal | None = None


@dataclass(frozen=True, kw_only=True)
class SiteItem:
    """One sellable row of ``GET /catalog/items``: an offer, or a simple product."""

    id: str
    site_id: int
    sku: str | None = None
    name: str
    section_id: str | None = None
    unit: SiteUnit
    ratio: Decimal = Decimal(1)
    description: str | None = None
    images: tuple[str, ...] = ()
    price: SitePrice | None = None
    stock: SiteStock | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemRows:
    """The rows one page of items became, and how many items it lost."""

    products: tuple[ProductRow, ...] = ()
    prices: tuple[PriceRow, ...] = ()
    stock: tuple[StockRow, ...] = ()
    skipped: int = 0


@dataclass(slots=True)
class ItemReader:
    """Reads pages of items for one pass, remembering what the pass has seen.

    Stateful on purpose and scoped to one pass. The same ``id`` twice in one
    INSERT is refused by Postgres ("cannot affect row a second time") and
    would fail the whole page, and across pages it would mean the site's
    stable ordering broke; either way the first occurrence wins and the rest
    are skipped with a warning.

    Attributes:
        price_type_ids: The price lists the pass announced. A price under any
            other would be stored against a price list the projection does
            not hold and never swept, so it is dropped.
        seen: Item ids already read in this pass.
    """

    price_type_ids: frozenset[str]
    seen: set[str] = field(default_factory=set)

    def read_page(self, data: object) -> ItemRows:
        """The rows of one page's ``data``.

        Raises:
            CatalogSourceReadError: ``data`` is not a list at all.
        """
        entries = _entries(data, "items")

        products: list[ProductRow] = []
        prices: list[PriceRow] = []
        stock: list[StockRow] = []
        skipped = 0

        for index, entry in enumerate(entries):
            try:
                item = _retort.load(entry, SiteItem)
            except LoadError as exc:
                reasons = "; ".join(load_error_reasons(exc, "the item"))
                logger.warning("site catalog: items[%d] skipped: %s", index, reasons)
                skipped += 1
                continue

            problem = self._problem(item)
            if problem is not None:
                logger.warning("site catalog: item %r skipped: %s", item.id, problem)
                skipped += 1
                continue

            self.seen.add(item.id)
            products.append(_product(item))

            price = self._price(item)
            if price is not None:
                prices.append(price)

            stock_row = _stock(item)
            if stock_row is not None:
                stock.append(stock_row)

        return ItemRows(
            products=tuple(products),
            prices=tuple(prices),
            stock=tuple(stock),
            skipped=skipped,
        )

    def _problem(self, item: SiteItem) -> str | None:
        """Why this item cannot become a product row, or ``None`` if it can."""
        problems = (
            (not item.id.strip(), "the id is blank"),
            (len(item.id) > MAX_ID_LENGTH, f"the id is over {MAX_ID_LENGTH} characters"),
            (item.id in self.seen, "the id was already read in this pass"),
            (not item.name.strip(), "the name is blank"),
            (
                len(item.name.strip()) > MAX_NAME_LENGTH,
                f"the name is over {MAX_NAME_LENGTH} characters",
            ),
            (not item.unit.name.strip(), "the unit has no name"),
            (
                len(item.unit.name.strip()) > MAX_UNIT_NAME_LENGTH,
                f"the unit name is over {MAX_UNIT_NAME_LENGTH} characters",
            ),
            (item.ratio <= 0, "the ratio is not positive"),
        )
        return next((reason for failed, reason in problems if failed), None)

    def _price(self, item: SiteItem) -> PriceRow | None:
        """The item's price row, if it has one under a price list of this pass."""
        price = item.price
        if price is None:
            return None

        if price.price_type_id not in self.price_type_ids:
            logger.warning(
                "site catalog: price of %r dropped: price type %r was not announced",
                item.id,
                price.price_type_id,
            )
            return None

        return PriceRow(
            product_id=item.id,
            price_type_id=price.price_type_id,
            amount=price.amount,
            currency=price.currency,
        )


def read_sections(data: object) -> tuple[CategoryRow, ...]:
    """The whole category tree, one row per section.

    Raises:
        CatalogSourceReadError: ``data`` is not a list of sections, an entry
            is broken, or an id repeats.
    """
    sections = _load_all(data, "sections", list[SiteSection])
    rows = tuple(
        CategoryRow(
            id=_required(section.id, f"sections[{index}].id"),
            parent_id=_optional(section.parent_id),
            name=_required(section.name, f"sections[{index}].name").strip(),
        )
        for index, section in enumerate(sections)
    )
    _refuse_duplicates((row.id for row in rows), "sections")
    return rows


def read_price_types(data: object) -> tuple[PriceTypeRow, ...]:
    """Every price list the catalog is priced in.

    Raises:
        CatalogSourceReadError: ``data`` is not a list of price types, an
            entry is broken, or an id repeats.
    """
    price_types = _load_all(data, "price-types", list[SitePriceType])
    rows = tuple(
        PriceTypeRow(
            id=_required(price_type.id, f"price-types[{index}].id"),
            name=_required(price_type.name, f"price-types[{index}].name").strip(),
            currency=_required(price_type.currency, f"price-types[{index}].currency"),
        )
        for index, price_type in enumerate(price_types)
    )
    _refuse_duplicates((row.id for row in rows), "price-types")
    return rows


def _product(item: SiteItem) -> ProductRow:
    return ProductRow(
        id=item.id,
        sku=_sku(item),
        name=item.name.strip(),
        category_id=_optional(item.section_id),
        unit_id=_optional(item.unit.code),
        unit_name=item.unit.name.strip(),
        unit_ratio=item.ratio,
        description=_optional(item.description),
        image_url=next((url for url in item.images if url.strip()), None),
    )


def _sku(item: SiteItem) -> str:
    """The article, or the site's own number where there is no usable one.

    An article over the column's width or with a control character in it is
    not one a customer could read out, and would fail the insert or the
    ``Sku`` an order line builds from it; the number is used then too, and the
    substitution is logged so the site's manager can fix the card.
    """
    fallback = str(item.site_id)
    sku = (item.sku or "").strip()

    if not sku:
        return fallback

    if len(sku) > MAX_SKU_LENGTH or not sku.isprintable():
        logger.warning(
            "site catalog: article of %r is unusable, using site id %s",
            item.id,
            fallback,
        )
        return fallback

    return sku


def _stock(item: SiteItem) -> StockRow | None:
    """A stock row for a counted item, and none for one nobody counts."""
    stock = item.stock
    if stock is None or stock.status == UNTRACKED_STOCK_STATUS:
        return None

    if stock.status not in COUNTED_STOCK_STATUSES:
        logger.warning(
            "site catalog: stock of %r has unknown status %r, shown as made to order",
            item.id,
            stock.status,
        )
        return None

    if stock.quantity is None:
        if stock.status == "in_stock":
            logger.warning(
                "site catalog: %r is in stock with no quantity, shown as made to order",
                item.id,
            )
            return None
        quantity = Decimal(0)
    else:
        quantity = max(stock.quantity, Decimal(0))

    return StockRow(
        product_id=item.id,
        warehouse_id=STOCK_WAREHOUSE_ID,
        quantity=quantity,
    )


def _entries(data: object, what: str) -> list[object]:
    if not isinstance(data, list):
        msg = f"The site's {what} listing is not a list."
        raise CatalogSourceReadError(msg)
    return data


def _load_all[T](data: object, what: str, shape: type[T]) -> T:
    try:
        return _retort.load(_entries(data, what), shape)
    except LoadError as exc:
        reasons = "; ".join(load_error_reasons(exc, what, root=what))
        msg = f"The site's {what} listing is not the contract: {reasons}."
        raise CatalogSourceReadError(msg) from exc


def _required(value: str, where: str) -> str:
    if not value.strip():
        msg = f"The site sent a blank {where}."
        raise CatalogSourceReadError(msg)
    return value


def _optional(value: str | None) -> str | None:
    """``None`` for an absent value and for a blank one, which mean the same."""
    if value is None or not value.strip():
        return None
    return value


def _refuse_duplicates(ids: Iterable[str], what: str) -> None:
    seen: set[str] = set()
    for identifier in ids:
        if identifier in seen:
            msg = f"The site's {what} listing names {identifier!r} twice."
            raise CatalogSourceReadError(msg)
        seen.add(identifier)
