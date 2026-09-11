import pytest

from goldy.domain.catalog.errors import (
    EmptyProductNameError,
    EmptySkuError,
    EmptySourceIdError,
    EmptyUnitOfMeasureError,
    TooLongProductNameError,
    TooLongSkuError,
    TooLongSourceIdError,
    TooLongUnitOfMeasureError,
)
from goldy.domain.catalog.values.category_id import CategoryId
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.catalog.values.product_name import MAX_PRODUCT_NAME_LENGTH, ProductName
from goldy.domain.catalog.values.sku import MAX_SKU_LENGTH, Sku
from goldy.domain.catalog.values.source_id import MAX_SOURCE_ID_LENGTH, SourceId
from goldy.domain.catalog.values.unit_of_measure import (
    MAX_UNIT_OF_MEASURE_NAME_LENGTH,
    UnitOfMeasure,
)
from tests.unit.factories.shop_factories import (
    make_money,
    make_priced_product,
    make_unit,
)

SOURCE_ID_TYPES: tuple[type[SourceId], ...] = (ProductId, CategoryId, PriceTypeId)
COMPOSITE_KEY: str = (
    "8a1b0c2d-3e4f-5061-7283-94a5b6c7d8e9#f0e1d2c3-b4a5-9687-7869-5a4b3c2d1e0f"
)


@pytest.mark.parametrize("blank", ("", "   ", "\t\n"))
def test_a_blank_article_is_refused(blank: str) -> None:
    """1C owns the article, but a blank one on a placed order is our defect."""
    with pytest.raises(EmptySkuError):
        Sku(value=blank)


def test_an_overlong_article_is_refused() -> None:
    with pytest.raises(TooLongSkuError):
        Sku(value="x" * (MAX_SKU_LENGTH + 1))


@pytest.mark.parametrize("blank", ("", "   "))
def test_a_blank_product_name_is_refused(blank: str) -> None:
    with pytest.raises(EmptyProductNameError):
        ProductName(value=blank)


def test_an_overlong_product_name_is_refused() -> None:
    with pytest.raises(TooLongProductNameError):
        ProductName(value="я" * (MAX_PRODUCT_NAME_LENGTH + 1))


@pytest.mark.parametrize("source_id_type", SOURCE_ID_TYPES)
def test_a_blank_catalog_identifier_is_refused(
    source_id_type: type[SourceId],
) -> None:
    """The rule is written once on the base and holds for all three."""
    with pytest.raises(EmptySourceIdError):
        source_id_type(value=" ")


@pytest.mark.parametrize("source_id_type", SOURCE_ID_TYPES)
def test_an_overlong_catalog_identifier_is_refused(
    source_id_type: type[SourceId],
) -> None:
    with pytest.raises(TooLongSourceIdError):
        source_id_type(value="x" * (MAX_SOURCE_ID_LENGTH + 1))


def test_a_composite_1c_key_fits_a_catalog_identifier() -> None:
    """The case the string was chosen for: 73 characters, which 64 would refuse.

    Once product variants are switched on in 1C the identifier arrives as
    ``guid#guid``, and a ``uuid`` column would break the import that day.
    """
    assert ProductId(value=COMPOSITE_KEY).value == COMPOSITE_KEY


def test_two_kinds_of_catalog_identifier_never_compare_equal() -> None:
    """Free from the dataclass: its ``__eq__`` demands the same class.

    A product and a category can perfectly well share a string, and comparing
    the two as equal is how a category id ends up looked up as a product.
    """
    assert ProductId(value="x") != CategoryId(value="x")
    assert ProductId(value="x") == ProductId(value="x")


def test_any_price_type_1c_invents_is_accepted() -> None:
    """A string rather than an enum: adding a price list in 1C is not a release."""
    assert PriceTypeId(value="опт-2027").value == "опт-2027"


def test_a_unit_of_measure_carries_both_the_reference_and_the_label() -> None:
    """The export needs the reference, the customer needs the label."""
    unit = make_unit(name="шт", source_id="1c-unit-796")

    assert unit.source_id == "1c-unit-796"
    assert str(unit) == "шт"


def test_a_unit_of_measure_is_built_positionally() -> None:
    """Pins the composite mapping down: SQLAlchemy rebuilds it by field order."""
    assert UnitOfMeasure("1c-unit-796", "шт") == make_unit()


def test_a_unit_of_measure_without_a_reference_is_accepted() -> None:
    """1C does not always hand one over, and the label is what is displayed."""
    assert UnitOfMeasure(None, "шт").name == "шт"


@pytest.mark.parametrize("blank", ("", "  "))
def test_a_unit_of_measure_without_a_name_is_refused(blank: str) -> None:
    """A quantity with no unit beside it tells the customer nothing."""
    with pytest.raises(EmptyUnitOfMeasureError):
        UnitOfMeasure("1c-unit-796", blank)


def test_an_overlong_unit_of_measure_name_is_refused() -> None:
    with pytest.raises(TooLongUnitOfMeasureError):
        UnitOfMeasure(None, "я" * (MAX_UNIT_OF_MEASURE_NAME_LENGTH + 1))


def test_an_overlong_unit_of_measure_reference_is_refused() -> None:
    """The same ceiling as ``SourceId``, restated because a composite cannot nest."""
    with pytest.raises(TooLongSourceIdError):
        UnitOfMeasure("x" * (MAX_SOURCE_ID_LENGTH + 1), "шт")


@pytest.mark.parametrize("blank", ("", "   "))
def test_a_unit_of_measure_with_a_blank_reference_is_refused(blank: str) -> None:
    """An absent reference is ``None``; an empty string is not the same thing.

    A missing attribute reaches us from a JSON fixture or an exchange message
    as ``""`` more often than as ``null``, and that value is not NULL in the
    column and points at nothing in 1C — which is exactly what ``SourceId``
    refuses, so the composite refuses it too.
    """
    with pytest.raises(EmptySourceIdError):
        UnitOfMeasure(blank, "шт")


def test_a_priced_product_carries_the_price_this_customer_pays() -> None:
    """The one place read-model primitives become values an order may keep."""
    priced = make_priced_product(index=3, price="49.50")

    assert priced.sku is not None
    assert priced.sku.value == "SKU-3"
    assert priced.unit == make_unit()
    assert priced.unit_price == make_money("49.50")


def test_a_product_1c_gave_no_article_is_still_a_priced_product() -> None:
    """The article is optional in 1C, and products without one are ordinary.

    A mandatory ``Sku`` here would not break the import — the projection builds
    no values — it would break the customer's "place order" button.
    """
    priced = make_priced_product(index=4, with_sku=False)

    assert priced.sku is None


def test_catalog_values_compare_by_value() -> None:
    assert Sku(value="A-1") == Sku(value="A-1")
    assert Sku(value="A-1") != Sku(value="A-2")
