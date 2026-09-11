"""The two decisions the projection writer makes on its own.

Everything else in this gateway is SQL, and SQL is what the integration suite
is for. What can be settled without a database is the pair of things computed
in Python before a statement is built: where a category sits in the tree the
batch describes, and whether this shop can price in the currency 1C
denominated a price list in.
"""

from goldy.domain.common.values.currency import Currency
from goldy.infrastructure.adapters.persistence import (
    sqlalchemy_catalog_projection_gateway as projection,
)
from tests.unit.factories.catalog_factories import make_category_id, make_category_row

PATH_SEPARATOR = projection.PATH_SEPARATOR
_placements = projection._placements
_is_supported = projection._is_supported


def test_a_root_group_is_its_own_path_at_depth_zero() -> None:
    placements = _placements((make_category_row(1),))

    assert placements[make_category_id(1)].path == make_category_id(1)
    assert placements[make_category_id(1)].depth == 0


def test_a_group_is_pathed_through_every_ancestor_in_the_batch() -> None:
    """The path is what a whole-subtree listing is selected by.

    1C puts products in the leaves, so a listing keyed on ``parent_id`` alone
    shows an empty group wherever that group has subgroups.
    """
    rows = (
        make_category_row(1),
        make_category_row(2, parent_index=1),
        make_category_row(3, parent_index=2),
    )

    placements = _placements(rows)

    assert placements[make_category_id(3)].path == PATH_SEPARATOR.join([
        make_category_id(1),
        make_category_id(2),
        make_category_id(3),
    ])
    assert placements[make_category_id(3)].depth == 2


def test_a_group_is_placed_whatever_order_the_batch_listed_it_in() -> None:
    """RabbitMQ promises no order, and a message is one batch either way."""
    child_first = _placements((
        make_category_row(2, parent_index=1),
        make_category_row(1),
    ))
    parent_first = _placements((
        make_category_row(1),
        make_category_row(2, parent_index=1),
    ))

    assert child_first[make_category_id(2)] == parent_first[make_category_id(2)]


def test_a_group_whose_parent_is_missing_sits_higher_rather_than_failing() -> None:
    """A broken snapshot is not worth refusing a whole catalog import over.

    The group simply appears one level up, which is visible on the storefront
    and fixed by the next export; refusing the batch would take the working
    part of the catalog down with the broken part.
    """
    placements = _placements((make_category_row(2, parent_index=99),))

    assert placements[make_category_id(2)].path == make_category_id(2)
    assert placements[make_category_id(2)].depth == 0


def test_a_cycle_in_the_batch_ends_the_walk_instead_of_hanging_it() -> None:
    """Two groups each other's parent is a broken export, not an outage."""
    rows = (
        make_category_row(1, parent_index=2),
        make_category_row(2, parent_index=1),
    )

    placements = _placements(rows)

    assert placements[make_category_id(1)].depth == 1
    assert placements[make_category_id(2)].depth == 1


def test_an_empty_batch_places_nothing() -> None:
    assert _placements(()) == {}


def test_a_currency_this_shop_knows_is_supported_however_1c_cased_it() -> None:
    """1C spells codes in upper case and the domain enum in lower."""
    assert _is_supported("RUB") is True
    assert _is_supported(" rub ") is True
    assert _is_supported(Currency.RUB.value) is True


def test_a_currency_this_shop_does_not_know_is_stored_unsupported() -> None:
    """Stored rather than dropped: a customer bound to it gets a plain refusal.

    Dropping the price list would hand that customer the default one instead,
    which is somebody else's prices shown without telling them.
    """
    assert _is_supported("KZT") is False
    assert _is_supported("") is False
