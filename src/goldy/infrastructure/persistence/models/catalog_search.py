"""The normalisation rule behind product search, written twice on purpose.

Two mechanisms answer two different questions. Morphology of the name — "дрели"
finding "дрель" — is something only a dictionary does, and the ``russian``
snowball configuration ships with Postgres. A fragment of an article, "123"
inside "AB-12345", is something a dictionary cannot do at all: that needs
trigrams, which also buy tolerance of typos.

Normalisation is a generated column rather than something computed on every
query, so each rule exists in two places — the SQL expression here and the
Python mirror beside it. That is unavoidable: Postgres computes the column and
Python normalises the search term before it is bound. The pair is what makes
them agree, and the character sets are shared between the two spellings so that
at least the alphabet cannot drift.

What can still drift is the shape of the expressions, and it would drift
silently: search would simply stop finding some articles, and no unit test
would notice. The duplicate is therefore held down by an integration test that
runs both implementations over a table of awkward inputs — ``AB-123``,
``ab 123``, ``ab123``, ``AB_123``, "Ёлка" against "елка", mixed case — and
compares what Python produced with what the database computed.

These mirrors are called only inside ``SqlAlchemyCatalogQueryGateway``, and
they are not exported outside ``goldy.infrastructure``: a query carries the
term exactly as the person typed it, and the application layer checks only its
length. Anything else would put the ORM into the layer that must not know one.

The full-text column is built over the *normalised* name rather than the raw
one, so a search term has to go through :func:`normalize_name` before it
reaches ``plainto_tsquery`` as well. One normalisation for both mechanisms is
the only version of this that cannot half-work.
"""

from typing import Final

SKU_SEPARATORS: Final[str] = "-_ ./"
"""Characters people put inside an article and then leave out when typing it."""

YO: Final[str] = "\N{CYRILLIC SMALL LETTER IO}"
YE: Final[str] = "\N{CYRILLIC SMALL LETTER IE}"
"""Spelled as escapes, because this is the one place the two must not be mixed.

A Cyrillic "ie" and a Latin "e" look identical in an editor, and a normalisation
rule written with the wrong one would fold nothing while looking correct.
"""

SEARCH_TEXT_CONFIGURATION: Final[str] = "russian"
"""The snowball configuration the full-text column and every query share."""

SKU_NORMALIZED_SQL: Final[str] = f"upper(translate(sku, '{SKU_SEPARATORS}', ''))"
"""Levels "AB-123", "ab 123" and "ab123" — how an article is actually typed."""

NAME_NORMALIZED_SQL: Final[str] = f"translate(lower(name), '{YO}', '{YE}')"
"""Folds the dotted Russian letter onto the plain one, which snowball leaves apart."""

SEARCH_VECTOR_SQL: Final[str] = (
    f"to_tsvector('{SEARCH_TEXT_CONFIGURATION}', {NAME_NORMALIZED_SQL})"
)
"""Morphology of the name, over the same normalised text the trigrams use."""

_SKU_SEPARATORS_TABLE: Final[dict[int, int | None]] = str.maketrans(
    "",
    "",
    SKU_SEPARATORS,
)


def normalize_sku(sku: str) -> str:
    """The Python mirror of :data:`SKU_NORMALIZED_SQL`."""
    return sku.translate(_SKU_SEPARATORS_TABLE).upper()


def normalize_name(name: str) -> str:
    """The Python mirror of :data:`NAME_NORMALIZED_SQL`."""
    return name.lower().replace(YO, YE)
