from dataclasses import dataclass

from goldy.domain.catalog.values.source_id import SourceId


@dataclass(frozen=True, kw_only=True)
class CategoryId(SourceId):
    """The id 1C knows a catalog section by.

    The tree arrives from 1C whole and is never edited here, so this identifies
    a row of the projection and nothing the domain owns.
    """
