from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy import RowMapping

    from goldy.application.common.ports.catalog import ResolvedPriceType
    from goldy.domain.catalog.values.priced_product import PricedProduct


class PricingRowMapper(Protocol):
    """Builds what the checkout keeps out of the rows the pricing reader fetches.

    The row-mapper twin of ``CatalogRowViewMapper``, kept apart because the
    output is a different kind of thing: not a view on its way to a screen but
    a domain value on its way into an order line. The projection is Core-only
    and stores primitives, so this is the boundary where a product name, an
    article and a price become validated values — the same job the type
    decorators do for every column a command gateway reads.

    Infrastructure, port and all, for the reason every row mapper is: the input
    is a ``sqlalchemy.RowMapping``.
    """

    @abstractmethod
    def to_priced_product(self, row: RowMapping) -> PricedProduct:
        """Reads ``product_id``, ``sku``, ``name``, the unit and the price.

        Raises:
            DomainFieldError: the projection holds a value the domain refuses.
        """
        raise NotImplementedError

    @abstractmethod
    def to_resolved_price_type(self, row: RowMapping) -> ResolvedPriceType:
        """Reads ``price_type_id`` and ``is_supported``."""
        raise NotImplementedError
