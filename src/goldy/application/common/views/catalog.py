from dataclasses import dataclass
from decimal import Decimal

from goldy.application.common.views.money import MoneyView


@dataclass(frozen=True, slots=True)
class CategoryView:
    """One node of the catalog tree, as the category screen draws it.

    Carries the denormalised ``path`` the projection stores rather than only
    ``parent_id``, because products in 1C sit in the leaves of the hierarchy:
    a listing keyed on ``parent_id`` alone shows an empty group wherever that
    group has subgroups. The path is what a whole-subtree listing is selected
    by, and presentation uses it to build a breadcrumb without a second query.
    """

    id: str
    parent_id: str | None
    name: str
    path: str
    depth: int

    @property
    def is_root(self) -> bool:
        """Whether this group sits at the top of the tree."""
        return self.parent_id is None


@dataclass(frozen=True, slots=True)
class CategoryListView:
    """One level of the tree together with the group it was opened from.

    Both halves in one view because the category screen needs both at once and
    a screen that fetched its heading separately would read the tree twice per
    render. ``parent`` is the group whose subgroups these are, and it is
    ``None`` at the top of the catalog, where there is no heading to draw.

    A group that vanished between one render and the next comes back as
    ``parent=None`` with no subgroups rather than as an error. Deactivating a
    category is an ordinary consequence of an import sweep, and a customer who
    tapped a button a second too late is owed an empty screen, not a refusal.
    """

    parent: CategoryView | None
    categories: tuple[CategoryView, ...]

    @property
    def is_root_level(self) -> bool:
        """Whether this is the top of the catalog rather than a group."""
        return self.parent is None

    @property
    def has_subgroups(self) -> bool:
        """Whether the screen has any buttons to draw above the listing."""
        return bool(self.categories)


@dataclass(frozen=True, slots=True)
class ProductListItemView:
    """One row of a storefront listing or of a set of search results.

    ``unit_price`` is optional and that is an ordinary case rather than a
    defect: there may be no row in the price projection for this customer's
    price type, and the join returns nothing. A listing prints "price on
    request" and hides "add to cart"; rendering a zero would read as "free",
    which is worse than saying nothing.

    ``stock`` is advisory. It is a projection of 1C with no reservation behind
    it, so nothing is ever hidden or refused on it — a product at zero is sold
    to order, and the screen says exactly that.
    """

    id: str
    sku: str | None
    name: str
    unit_name: str
    unit_price: MoneyView | None
    stock: Decimal | None

    @property
    def is_priced(self) -> bool:
        """Whether this customer's price type prices this product at all."""
        return self.unit_price is not None

    @property
    def is_in_stock(self) -> bool:
        """Shown as a badge, never used to hide a button."""
        return self.stock is not None and self.stock > 0


@dataclass(frozen=True, slots=True)
class ProductView:
    """A product card, priced for the customer looking at it.

    Holds the whole ``description`` rather than a prepared excerpt: the card is
    rendered as a photo with a caption and Telegram refuses a caption over 1024
    characters, so how much of it fits is a presentation decision and changing
    that budget must not mean changing a query.
    """

    id: str
    sku: str | None
    name: str
    full_name: str | None
    category_id: str | None
    category_name: str | None
    unit_name: str
    unit_ratio: Decimal
    description: str | None
    image_url: str | None
    unit_price: MoneyView | None
    stock: Decimal | None
    is_active: bool

    @property
    def is_priced(self) -> bool:
        """Whether this customer's price type prices this product at all."""
        return self.unit_price is not None

    @property
    def is_in_stock(self) -> bool:
        """Shown as a badge, never used to hide a button."""
        return self.stock is not None and self.stock > 0

    @property
    def has_description(self) -> bool:
        """Whether the "description" button has anything to open."""
        return bool(self.description and self.description.strip())


@dataclass(frozen=True, slots=True)
class ProductListView:
    """One page of a listing together with the count the pager needs.

    The total comes back with the page rather than from a second call, because
    every caller of this needs both: paging is server-side, so the page counter
    is drawn from the same request that drew the rows.
    """

    products: tuple[ProductListItemView, ...]
    total: int


@dataclass(frozen=True, slots=True)
class ProductSearchView:
    """One page of search results, plus the one shortcut the screen may take.

    ``exact_sku_product_id`` is set only when the normalised search term
    matched the article of exactly one product, which is the single case where
    opening the card straight away is safe. Any other number of matches — none,
    two, a hundred — is a list, and that holds whether or not the shop keeps
    its articles unique, because 1C does not make it.
    """

    products: tuple[ProductListItemView, ...]
    total: int
    exact_sku_product_id: str | None

    @property
    def is_empty(self) -> bool:
        """An empty result is a screen of its own, not an error."""
        return not self.products


@dataclass(frozen=True, slots=True)
class PriceTypeView:
    """The price type a customer buys at, resolved in one query.

    Deliberately narrow. The binding is keyed by phone number in the
    projection and falls back to the price type configured for the bot, so by
    the time this is built the question "which price list" is already answered
    and only two facts are left to carry.

    ``is_supported`` is false when 1C sent a currency this service does not
    know. Handing back the default price list instead would show that customer
    somebody else's prices without telling them, so the provider turns this
    flag into a refusal rather than a fallback.
    """

    price_type_id: str
    is_supported: bool


@dataclass(frozen=True, slots=True)
class PricedProductView:
    """A product as the pricing read model has it, before it becomes a value.

    This is the raw side of the boundary ``PricedProduct`` sits on the other
    side of: primitives read out of the projection, which an application
    service validates into domain values before an order is allowed to keep
    them as a snapshot.

    ``unit_price`` may be missing for the same reason it may be missing in a
    listing — no row under this customer's price type. At checkout that is not
    cosmetic, and it is the one and only source of ``ProductNotPricedError``.
    """

    product_id: str
    sku: str | None
    name: str
    unit_id: str | None
    unit_name: str
    unit_price: MoneyView | None

    @property
    def is_priced(self) -> bool:
        """Whether this product can be turned into an order line at all."""
        return self.unit_price is not None


@dataclass(frozen=True, slots=True)
class CatalogImportResponse:
    """Outcome of one import batch, for the seeder and the consumer log.

    ``discarded`` counts rows the import refused before the customer could see
    them — a price of zero, which reads as "free", and prices under a price
    type whose currency this service does not know.
    """

    batch_id: str
    scope: str
    accepted: int
    discarded: int


@dataclass(frozen=True, slots=True)
class CatalogFinalizationResponse:
    """Outcome of one sweep, for the same log.

    ``swept`` counts rows the batch did not mention. What that meant depends on
    the scope and the difference matters: products and categories are
    deactivated and kept forever because placed orders point at them, while
    prices and stock are deleted, because a price withdrawn in 1C that stays in
    the projection is a price the shop does not actually offer.
    """

    batch_id: str
    scope: str
    swept: int
