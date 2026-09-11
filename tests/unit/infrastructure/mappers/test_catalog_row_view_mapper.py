from decimal import Decimal

from goldy.infrastructure.mappers.sqlalchemy_catalog_row_view_mapper import (
    SqlAlchemyCatalogRowViewMapper,
)
from tests.unit.factories.catalog_row_factories import (
    make_category_projection_row,
    make_listing_row,
    make_price_type_projection_row,
    make_priced_product_row,
    make_product_card_row,
)

MAPPER = SqlAlchemyCatalogRowViewMapper()


def test_a_product_without_a_price_is_offered_on_request_rather_than_free() -> None:
    """A zero here would be rendered as free, on every screen, forever.

    The outer join against the prices returns nothing for a product this
    customer's price type does not price, and that is an ordinary state. The
    decision "absent, not zero" is made once here so that no screen has to
    make it again.
    """
    item = MAPPER.to_product_list_item_view(make_listing_row(price=None))

    assert item.unit_price is None
    assert item.is_priced is False


def test_a_priced_row_takes_the_currency_off_the_price_itself() -> None:
    """The reason the currency is duplicated onto the price row at all.

    Reading it from the price type instead would make every storefront page
    drag one more join along for one column.
    """
    item = MAPPER.to_product_list_item_view(make_listing_row(price="19.99"))

    assert item.unit_price is not None
    assert item.unit_price.amount == Decimal("19.99")
    assert item.unit_price.currency == "rub"


def test_stock_summed_over_the_warehouses_reaches_the_listing() -> None:
    stocked = MAPPER.to_product_list_item_view(make_listing_row(stock="12.500"))
    withdrawn = MAPPER.to_product_list_item_view(make_listing_row(stock=None))

    assert stocked.stock == Decimal("12.500")
    assert stocked.is_in_stock is True
    assert withdrawn.stock is None
    assert withdrawn.is_in_stock is False


def test_a_group_carries_the_path_the_import_computed() -> None:
    """Presentation builds a breadcrumb from this without a second query."""
    root = MAPPER.to_category_view(make_category_projection_row(1))
    child = MAPPER.to_category_view(make_category_projection_row(2, parent_index=1))

    assert (root.path, root.depth, root.is_root) == ("1c-category-1", 0, True)
    assert child.path == "1c-category-1/1c-category-2"
    assert (child.depth, child.is_root) == (1, False)


def test_the_card_names_the_group_it_was_opened_from() -> None:
    """``category_name`` is labelled because the plain name is the product's."""
    view = MAPPER.to_product_view(make_product_card_row(category_index=3))

    assert view.name == "Product 1"
    assert view.category_id == "1c-category-3"
    assert view.category_name == "Group 3"


def test_a_card_for_a_withdrawn_product_still_reports_it_as_withdrawn() -> None:
    """A card is opened from last spring's order as well as from a listing."""
    view = MAPPER.to_product_view(make_product_card_row(is_active=False))

    assert view.is_active is False


def test_a_product_nobody_grouped_keeps_neither_id_nor_group_name() -> None:
    view = MAPPER.to_product_view(make_product_card_row(category_index=None))

    assert view.category_id is None
    assert view.category_name is None


def test_a_priced_row_says_which_product_it_is_about() -> None:
    """``product_id`` is labelled: a priced row carries two ids and one name."""
    view = MAPPER.to_priced_product_view(make_priced_product_row())

    assert view.product_id == "1c-product-1"
    assert view.unit_id == "1c-unit-796"
    assert view.is_priced is True


def test_a_product_the_price_list_skips_cannot_become_an_order_line() -> None:
    """The one and only source of ``ProductNotPricedError`` at checkout."""
    view = MAPPER.to_priced_product_view(make_priced_product_row(price=None))

    assert view.unit_price is None
    assert view.is_priced is False


def test_a_product_without_an_article_keeps_none() -> None:
    """``None`` must not become the string ``"None"`` on the way out."""
    view = MAPPER.to_priced_product_view(make_priced_product_row(with_sku=False))

    assert view.sku is None


def test_a_price_list_in_a_currency_we_do_not_know_comes_back_unsupported() -> None:
    """Stored rather than dropped, so the customer gets a plain refusal."""
    supported = MAPPER.to_price_type_view(make_price_type_projection_row())
    unknown = MAPPER.to_price_type_view(
        make_price_type_projection_row("1c-price-type-usd", is_supported=False),
    )

    assert supported.is_supported is True
    assert unknown.price_type_id == "1c-price-type-usd"
    assert unknown.is_supported is False
