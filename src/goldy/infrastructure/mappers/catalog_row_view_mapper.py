from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy import RowMapping

    from goldy.application.common.views.catalog import (
        CategoryView,
        PriceTypeView,
        PricedProductView,
        ProductListItemView,
        ProductView,
    )


class CatalogRowViewMapper(Protocol):
    """Builds the catalog read model straight from result rows.

    Kept in the infrastructure layer, port and all, because its input is a
    ``sqlalchemy.RowMapping``: declaring this among the application ports would
    put the ORM in the layer that is meant not to know one. The precedent is
    ``UserRowViewMapper``, and the reason is the same.

    Unlike that one, nothing here has to be unwrapped. The projection is
    Core-only and its columns carry no type decorators, so a row arrives as the
    primitives 1C sent and leaves as the primitives a view carries.

    The key names below are the contract between this mapper and the gateways
    that feed it, and they are the plain column names wherever a query can use
    them. Three are labelled because the plain name would be ambiguous:
    ``stock`` is a sum over warehouses rather than a column, ``category_name``
    would collide with the product's own ``name``, and ``product_id`` says
    which id a priced row is about.
    """

    @abstractmethod
    def to_category_view(self, row: RowMapping) -> CategoryView:
        """Reads ``id``, ``parent_id``, ``name``, ``path`` and ``depth``."""
        raise NotImplementedError

    @abstractmethod
    def to_product_list_item_view(self, row: RowMapping) -> ProductListItemView:
        """Reads ``id``, ``sku``, ``name``, ``unit_name``, the price and ``stock``."""
        raise NotImplementedError

    @abstractmethod
    def to_product_view(self, row: RowMapping) -> ProductView:
        """Reads the whole card, plus ``category_name``, the price and ``stock``."""
        raise NotImplementedError

    @abstractmethod
    def to_priced_product_view(self, row: RowMapping) -> PricedProductView:
        """Reads ``product_id``, ``sku``, ``name``, the unit and the price."""
        raise NotImplementedError

    @abstractmethod
    def to_price_type_view(self, row: RowMapping) -> PriceTypeView:
        """Reads ``price_type_id`` and ``is_supported``."""
        raise NotImplementedError
