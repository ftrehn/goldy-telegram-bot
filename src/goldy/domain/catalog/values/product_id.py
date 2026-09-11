from dataclasses import dataclass

from goldy.domain.catalog.values.source_id import SourceId


@dataclass(frozen=True, kw_only=True)
class ProductId(SourceId):
    """The id 1C knows a product by — a reference to its own object.

    We never mint one, which is why this package has no id generator and must
    not grow one: a product identifier produced here would name nothing in the
    source the catalog actually comes from.
    """
