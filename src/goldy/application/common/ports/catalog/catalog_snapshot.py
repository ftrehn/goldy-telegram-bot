from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class CatalogScopeKind(StrEnum):
    """Which part of the projection a batch is talking about.

    The scope is what makes sweeping safe. "Whatever this batch did not
    mention is gone" is only true within the part of the projection the batch
    was about: a single price list arriving would otherwise wipe every other
    one.
    """

    CATEGORIES = "categories"
    PRODUCTS = "products"
    PRICE_TYPES = "price_types"
    PRICES = "prices"
    STOCK = "stock"
    BINDINGS = "bindings"


@dataclass(frozen=True, kw_only=True)
class CatalogScope:
    """What a batch covers, and therefore what finalising it may sweep.

    ``price_type_id`` and ``warehouse_id`` narrow the sweep further, and they
    are not optional out of politeness: deleting every price row a batch did
    not mention, when the batch carried one price list, would delete all the
    others. They are set for the ``PRICES`` and ``STOCK`` kinds respectively
    and left unset everywhere else.

    Plain strings rather than value objects, because the projection is
    Core-only: nothing here is ever built into a domain value on its way in.
    """

    kind: CatalogScopeKind
    price_type_id: str | None = None
    warehouse_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class CategoryRow:
    """One group of the 1C nomenclature reference.

    Groups and products never share a table and never share a message: an
    element that is a group arrives here, an element that is a product arrives
    as a :class:`ProductRow`. That is a clause of the exchange contract rather
    than a flag on a row.

    There is no ``path`` or ``depth`` here, although the projection stores
    both. They are computed where they are written, from the batch as a whole,
    which is possible only because the contract requires the category snapshot
    to be complete in a single message.
    """

    id: str
    parent_id: str | None
    name: str
    source_changed_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class ProductRow:
    """One product of the 1C nomenclature reference."""

    id: str
    sku: str | None
    name: str
    full_name: str | None = None
    category_id: str | None = None
    unit_id: str | None = None
    unit_name: str
    unit_ratio: Decimal = Decimal(1)
    description: str | None = None
    image_url: str | None = None
    source_changed_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class PriceTypeRow:
    """One price list, as 1C names and denominates it.

    ``currency`` arrives as 1C spells it and is not checked here. Whether this
    service understands it is decided where the row is written, and a price
    list in a currency we do not know is stored unsupported rather than
    dropped — a customer bound to it gets a plain refusal instead of somebody
    else's roubles.
    """

    id: str
    name: str
    currency: str
    source_changed_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class PriceRow:
    """What one product costs under one price list.

    The currency is duplicated here although the price list already carries it.
    That is deliberate denormalisation: without it every storefront page would
    drag an extra join along for one column, and the currency of a price list
    changes approximately never — and changes through this same import, which
    writes both rows.
    """

    product_id: str
    price_type_id: str
    amount: Decimal
    currency: str
    source_changed_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class StockRow:
    """How much of one product is free to sell at one warehouse.

    ``quantity`` is the **free** remainder, computed on the 1C side. On hand
    and reserved are not stored separately and will not be — that would be two
    columns and a second question the bot cannot answer correctly.

    1C gives no warehouse breakdown today, so the consumer writes a fixed
    ``'*'``; the storefront query sums with a group-by from the first day, so
    real warehouses appearing changes neither the SQL nor this contract.
    """

    product_id: str
    warehouse_id: str
    quantity: Decimal
    source_changed_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class PriceTypeBindingRow:
    """Which price list a person buys at, keyed by their phone number.

    Not by ``user_id``, and that is the whole point of the table. In 1C the
    price list belongs to a counterparty, and a counterparty may well not have
    registered in the bot yet — a row keyed by user id would have nowhere to go
    and the message would be dropped, after which the customer would silently
    get default prices forever, because nobody re-sends bindings.

    ``source_counterparty_id`` exists so the consumer need not resolve the
    counterparty again on every message. It reaches no query and no domain
    object: there is no counterparty in this domain, literally.
    """

    phone_number: str
    price_type_id: str
    source_counterparty_id: str | None = None
    source_changed_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class CatalogSnapshot:
    """One batch of catalog data, with the mark that identifies it.

    A **batch**, not the whole catalog. 1C sends its nomenclature in parts and
    exports prices and stock separately from the reference itself, so "whatever
    is not in the snapshot is gone" applied per call would let the second batch
    wipe the first. Taking data in and sweeping what is stale are therefore two
    separate commands from the start.

    ``batch_id`` is written onto every row this snapshot touches, which is what
    the sweep afterwards selects by.
    """

    batch_id: str
    scope: CatalogScope
    categories: tuple[CategoryRow, ...] = ()
    products: tuple[ProductRow, ...] = ()
    price_types: tuple[PriceTypeRow, ...] = ()
    prices: tuple[PriceRow, ...] = ()
    stock: tuple[StockRow, ...] = ()
    price_type_bindings: tuple[PriceTypeBindingRow, ...] = ()
