"""Where a priced row of the projection becomes the values an order line keeps.

The boundary the type decorators hold for every command gateway, held here by
hand for the pricing reader: primitives in, validated domain values out, and a
refusal for what the domain refuses. The rows come from the query the
integration suite exercises; what is decided in Python is which value each
column becomes.
"""

from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import RowMapping

from goldy.application.error import UnsupportedPriceTypeError
from goldy.domain.catalog.errors import EmptyProductNameError
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.errors import NegativeMoneyAmountError
from goldy.domain.common.values.money import Money
from goldy.infrastructure.mappers.sqlalchemy_pricing_row_mapper import (
    SqlAlchemyPricingRowMapper,
)
from tests.unit.factories.catalog_row_factories import (
    make_price_type_projection_row,
    make_priced_product_row,
)
from tests.unit.factories.shop_factories import make_product_id, make_unit

MAPPER = SqlAlchemyPricingRowMapper()


def test_a_priced_row_becomes_the_values_a_line_is_snapshotted_from() -> None:
    """``product_id`` is labelled: a priced row carries two ids and one name."""
    priced = MAPPER.to_priced_product(make_priced_product_row(price="49.50"))

    assert priced.product_id == make_product_id(1)
    assert priced.sku.value == "SKU-1"
    assert priced.name.value == "Product 1"
    assert priced.unit == make_unit()
    assert priced.unit_price == Money(Decimal("49.50"), Currency.RUB)


def test_the_currency_is_read_however_1c_spelled_it() -> None:
    row = make_priced_product_row(currency=Currency.USD)

    priced = MAPPER.to_priced_product(row)

    assert priced.unit_price.currency is Currency.USD


def test_a_currency_this_shop_cannot_price_in_is_refused_not_substituted() -> None:
    """The import marks such lists unsupported; reaching here means they disagree."""
    row = _row_with(currency="GBP")

    with pytest.raises(UnsupportedPriceTypeError):
        MAPPER.to_priced_product(row)


def test_what_the_domain_refuses_is_refused_at_the_boundary() -> None:
    """A blank name or a nonsensical price must not reach an order as a snapshot."""
    with pytest.raises(EmptyProductNameError):
        MAPPER.to_priced_product(_row_with(name="   "))

    with pytest.raises(NegativeMoneyAmountError):
        MAPPER.to_priced_product(make_priced_product_row(price="-1.00"))


def test_a_price_list_in_a_currency_we_do_not_know_comes_back_unsupported() -> None:
    """Stored rather than dropped, so the customer gets a plain refusal."""
    supported = MAPPER.to_resolved_price_type(make_price_type_projection_row())
    unknown = MAPPER.to_resolved_price_type(
        make_price_type_projection_row("1c-price-type-usd", is_supported=False),
    )

    assert supported.is_supported is True
    assert unknown.price_type_id.value == "1c-price-type-usd"
    assert unknown.is_supported is False


def _row_with(**columns: object) -> RowMapping:
    """An ordinary priced row with one column overwritten."""
    return cast("RowMapping", {**make_priced_product_row(), **columns})
