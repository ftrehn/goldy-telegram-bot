from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.catalog import ProductView


@dataclass(frozen=True, slots=True)
class GetProductQuery(Query[ProductView]):
    """One product card, priced for whoever opened it."""

    product_id: str
