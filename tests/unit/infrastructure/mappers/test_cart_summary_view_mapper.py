from goldy.infrastructure.mappers.adaptix_cart_summary_view_mapper import (
    AdaptixCartSummaryViewMapper,
)
from tests.unit.factories.shop_factories import make_cart, make_product_id


def test_the_counts_come_from_the_aggregate() -> None:
    """Two properties, not two fields — adaptix has to be told about both."""
    cart = make_cart({1: 3, 2: 2})

    view = AdaptixCartSummaryViewMapper().to_view(cart, make_product_id(2))

    assert view.line_count == 2
    assert view.total_quantity == 5


def test_the_changed_product_crosses_as_text() -> None:
    """The view leaves the domain, so no ``ProductId`` may ride along in it."""
    cart = make_cart({1: 1})

    view = AdaptixCartSummaryViewMapper().to_view(cart, make_product_id(1))

    assert view.changed_product_id == "1c-product-1"


def test_a_command_that_touched_everything_names_nothing() -> None:
    cart = make_cart()

    view = AdaptixCartSummaryViewMapper().to_view(cart, None)

    assert view.changed_product_id is None
    assert view.is_empty
