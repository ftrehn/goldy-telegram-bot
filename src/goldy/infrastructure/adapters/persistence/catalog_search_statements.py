"""The SQL of the storefront search — what counts as a hit, and in what order.

Pure functions, like the listing statements beside them. Search shares not one
step with ordering by name or by price, which is why it is its own module and
its own query rather than a flag on the listing.
"""

from typing import Final

from sqlalchemy import ColumnElement, case, func, or_

from goldy.infrastructure.adapters.persistence.catalog_listing_statements import (
    LIKE_ESCAPE,
    escape_like,
)
from goldy.infrastructure.persistence.models import (
    SEARCH_TEXT_CONFIGURATION,
    catalog_products_table,
)

MIN_TRIGRAM_LENGTH: Final[int] = 3
"""Below this a GIN trigram index cannot be used at all, so the query changes.

Two characters produce no trigram, and a substring match on them would be a
sequential scan of the whole catalog. A prefix match is what is left, and it is
what somebody typing two characters meant anyway.
"""


def search_match(sku_term: str, name_term: str) -> ColumnElement[bool]:
    """What counts as a hit, by two mechanisms that answer two questions.

    A fragment of an article is trigrams and nothing else; morphology of the
    name is a dictionary and nothing else. Both are asked, and the ranking
    decides which of them mattered.

    Under three characters neither index applies and the query degrades to a
    prefix match: a substring match on two characters is a sequential scan of
    the catalog, and somebody typing two characters is typing the start of
    something.
    """
    if len(sku_term) < MIN_TRIGRAM_LENGTH:
        return or_(
            catalog_products_table.c.sku_normalized.like(
                f"{escape_like(sku_term)}%",
                escape=LIKE_ESCAPE,
            ),
            catalog_products_table.c.name_normalized.like(
                f"{escape_like(name_term)}%",
                escape=LIKE_ESCAPE,
            ),
        )

    return or_(
        catalog_products_table.c.sku_normalized.like(
            f"%{escape_like(sku_term)}%",
            escape=LIKE_ESCAPE,
        ),
        catalog_products_table.c.search_vector.op("@@", is_comparison=True)(
            tsquery(name_term),
        ),
        catalog_products_table.c.name_normalized.op("%", is_comparison=True)(name_term),
    )


def search_ranking(sku_term: str, name_term: str) -> tuple[ColumnElement[object], ...]:
    """Three steps, in the order a person expects them.

    An exact article first, because somebody who typed one typed it to find
    that product and nothing else. Then the full-text rank, which knows that
    "дрели" is "дрель". Then trigram similarity, which is what finds a name
    with a letter missing from it.

    This is an ordering over the projection and not a business rule, which is
    why it lives here.
    """
    exact_article = case(
        (catalog_products_table.c.sku_normalized == sku_term, 0),
        else_=1,
    )

    return (
        exact_article.asc(),
        func.ts_rank(catalog_products_table.c.search_vector, tsquery(name_term)).desc(),
        func.similarity(catalog_products_table.c.name_normalized, name_term).desc(),
        catalog_products_table.c.name.asc(),
        catalog_products_table.c.id.asc(),
    )


def tsquery(name_term: str) -> ColumnElement[object]:
    """The search term as a full-text query, over the same normalised text.

    The generated column is built from the normalised name, so the term has to
    reach ``plainto_tsquery`` normalised too. One normalisation for both
    mechanisms is the only version of this that cannot half-work.
    """
    return func.plainto_tsquery(SEARCH_TEXT_CONFIGURATION, name_term)
