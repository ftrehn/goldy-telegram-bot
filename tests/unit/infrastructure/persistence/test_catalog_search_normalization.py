"""The Python half of the normalisation rule product search is built on.

The rule exists twice: Postgres computes the generated columns, and Python
normalises the term before it is bound. Only the Python half can be tested
without a database, and what it is worth pinning here is the behaviour a
customer feels — that the separators people leave out of an article do not
matter, and that the dotted Russian letter does not split a name in two.

That the two halves *agree* is a different question and needs both of them
running, which is why it belongs to an integration test over a real table. What
is checked here besides the behaviour is only that the alphabets have not
drifted apart: both spellings are built from the same constants, and a test
that restated the character set would drift along with whichever half it was
copied from.
"""

from goldy.infrastructure.persistence.models.catalog_search import (
    NAME_NORMALIZED_SQL,
    SEARCH_TEXT_CONFIGURATION,
    SEARCH_VECTOR_SQL,
    SKU_NORMALIZED_SQL,
    SKU_SEPARATORS,
    YE,
    YO,
    normalize_name,
    normalize_sku,
)


def test_an_article_is_found_however_its_separators_were_typed() -> None:
    """A person typing an article leaves out whichever separators they like."""
    typed = ["AB-12345", "ab 12345", "ab12345", "AB_12345", "ab.12345", "ab/12345"]

    normalized = {normalize_sku(value) for value in typed}

    assert normalized == {"AB12345"}


def test_every_separator_the_rule_names_is_actually_removed() -> None:
    """The character set is shared with the SQL, so the list cannot be copied."""
    article = SKU_SEPARATORS.join(["A", "B", "1"])

    assert normalize_sku(article) == "AB1"


def test_an_article_of_digits_alone_survives_untouched() -> None:
    """Upper-casing digits is a no-op, and shortening one would break search."""
    assert normalize_sku("12345") == "12345"


def test_a_name_is_folded_to_one_case_and_one_spelling_of_yo() -> None:
    """The dotted letter and the plain one are one word to everybody but a collation."""
    assert normalize_name("Ёлка") == normalize_name("елка") == "елка"


def test_the_dotted_letter_is_folded_inside_a_word_as_well() -> None:
    assert normalize_name("Королёв") == "королев"


def test_a_latin_name_is_lower_cased_and_otherwise_left_alone() -> None:
    """Snowball does the morphology; normalisation only levels the spelling."""
    assert normalize_name("Bosch GSB 13 RE") == "bosch gsb 13 re"


def test_the_sql_mirror_is_built_from_the_same_character_sets() -> None:
    """Two spellings of one rule, held together by shared constants.

    The expressions themselves can still drift, and silently — search would
    simply stop finding some articles. That is what the integration test over a
    real table is for; what cannot be allowed to drift here is the alphabet,
    because a Cyrillic "ie" and a Latin "e" look identical in an editor.
    """
    assert SKU_SEPARATORS in SKU_NORMALIZED_SQL
    assert YO in NAME_NORMALIZED_SQL
    assert YE in NAME_NORMALIZED_SQL
    assert YO != YE


def test_the_full_text_column_is_built_over_the_normalised_name() -> None:
    """One normalisation for both mechanisms is the only version that works.

    The trigram index and the full-text index have to see the same text; if the
    vector were built over the raw name, a term normalised on its way into
    ``plainto_tsquery`` would miss every name spelled with the dotted letter.
    """
    assert NAME_NORMALIZED_SQL in SEARCH_VECTOR_SQL
    assert SEARCH_TEXT_CONFIGURATION in SEARCH_VECTOR_SQL
