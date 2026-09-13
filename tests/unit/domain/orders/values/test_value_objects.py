from datetime import UTC, datetime
from uuid import UUID

import pytest

from goldy.domain.orders.errors import (
    EmptyCancellationReasonError,
    EmptyDeliveryAddressError,
    EmptyOrderCommentError,
    EmptyOrderNumberError,
    ForeignDeliveryAddressError,
    IncompleteDeliveryAddressError,
    InvalidOrderNumberFormatError,
    TooLongCancellationReasonError,
    TooLongDeliveryAddressError,
    TooLongOrderCommentError,
    TooShortDeliveryAddressError,
)
from goldy.domain.orders.values.cancellation_reason import (
    MAX_CANCELLATION_REASON_LENGTH,
    CancellationReason,
)
from goldy.domain.orders.values.delivery_address import (
    MAX_DELIVERY_ADDRESS_LENGTH,
    MIN_DELIVERY_ADDRESS_LENGTH,
    DeliveryAddress,
)
from goldy.domain.orders.values.order_comment import (
    MAX_ORDER_COMMENT_LENGTH,
    OrderComment,
)
from goldy.domain.orders.values.order_number import OrderNumber
from goldy.domain.orders.values.recipient import Recipient
from goldy.domain.users.errors import EmptyFirstNameError
from tests.unit.factories.domain_factories import make_phone_number
from tests.unit.factories.shop_factories import make_recipient


@pytest.mark.parametrize("value", ("240913-3K7QXA", "000101-000000", "991231-ZZZZZZ"))
def test_an_order_number_is_a_day_and_six_readable_characters(value: str) -> None:
    assert OrderNumber(value=value).value == value


@pytest.mark.parametrize(
    "value",
    ("1000", "240913-3k7qxa", "240913-3K7QXAB", "240913-3K7QX", "240913-3I7QXA", "№1043"),
)
def test_a_number_outside_the_format_is_refused(value: str) -> None:
    """Lower case, a missing character and the letters the alphabet leaves out.

    Prefixes and padding are how presentation shows it, not what is stored.
    """
    with pytest.raises(InvalidOrderNumberFormatError):
        OrderNumber(value=value)


def test_a_number_is_derived_from_the_day_and_the_id() -> None:
    """No sequence: the same id placed at the same moment always spells the same."""
    placed_at = datetime(2024, 9, 13, 10, 30, tzinfo=UTC)
    order_id = UUID(int=0x3FFFFFFF)

    number = OrderNumber.derive(placed_at=placed_at, order_id=order_id)

    assert number.value == "240913-ZZZZZZ"
    assert number == OrderNumber.derive(placed_at=placed_at, order_id=order_id)


def test_the_number_takes_its_day_in_utc() -> None:
    """Every timestamp in the service keeps UTC, and the prefix follows them."""
    late_evening_in_moscow = datetime.fromisoformat("2024-09-14T01:30:00+03:00")

    number = OrderNumber.derive(placed_at=late_evening_in_moscow, order_id=UUID(int=1))

    assert number.value.startswith("240913-")


def test_two_ids_spell_two_numbers() -> None:
    placed_at = datetime(2024, 9, 13, tzinfo=UTC)

    first = OrderNumber.derive(placed_at=placed_at, order_id=UUID(int=1))
    second = OrderNumber.derive(placed_at=placed_at, order_id=UUID(int=2))

    assert first != second


def test_a_blank_order_number_is_refused() -> None:
    with pytest.raises(EmptyOrderNumberError):
        OrderNumber(value="   ")


def test_a_blank_delivery_address_is_refused() -> None:
    with pytest.raises(EmptyDeliveryAddressError):
        DeliveryAddress(value="")


@pytest.mark.parametrize("value", ("дом", "   дом    "))
def test_an_address_too_short_to_deliver_to_is_refused(value: str) -> None:
    """Padding it with spaces must not get it past the lower bound either."""
    with pytest.raises(TooShortDeliveryAddressError):
        DeliveryAddress(value=value)


def test_an_address_of_exactly_the_minimum_length_is_accepted() -> None:
    value = "я" * (MIN_DELIVERY_ADDRESS_LENGTH - 1) + "1"

    assert DeliveryAddress(value=value).value == value


@pytest.mark.parametrize("value", ("New York, 5th Avenue 1", "Washington DC 20500"))
def test_an_address_outside_russia_is_refused(value: str) -> None:
    """Delivery is within Russia, and a Russian courier reads Cyrillic."""
    with pytest.raises(ForeignDeliveryAddressError):
        DeliveryAddress(value=value)


def test_an_address_without_a_building_number_is_refused() -> None:
    with pytest.raises(IncompleteDeliveryAddressError):
        DeliveryAddress(value="Москва, улица Тверская")


def test_an_address_in_cyrillic_with_a_building_is_accepted() -> None:
    value = "Санкт-Петербург, Невский пр., д. 28, кв. 7"

    assert DeliveryAddress(value=value).value == value


def test_an_overlong_address_is_refused() -> None:
    with pytest.raises(TooLongDeliveryAddressError):
        DeliveryAddress(value="я1" * (MAX_DELIVERY_ADDRESS_LENGTH // 2 + 1))


def test_a_blank_order_comment_is_refused() -> None:
    """No comment is no ``OrderComment`` at all, not an empty one."""
    with pytest.raises(EmptyOrderCommentError):
        OrderComment(value="  ")


def test_an_overlong_order_comment_is_refused() -> None:
    with pytest.raises(TooLongOrderCommentError):
        OrderComment(value="x" * (MAX_ORDER_COMMENT_LENGTH + 1))


def test_a_blank_cancellation_reason_is_refused() -> None:
    with pytest.raises(EmptyCancellationReasonError):
        CancellationReason(value=" ")


def test_an_overlong_cancellation_reason_is_refused() -> None:
    with pytest.raises(TooLongCancellationReasonError):
        CancellationReason(value="x" * (MAX_CANCELLATION_REASON_LENGTH + 1))


def test_a_recipient_needs_a_name_it_can_be_called_by() -> None:
    """The name rules are ``FullName``'s, restated nowhere."""
    with pytest.raises(EmptyFirstNameError):
        make_recipient(first_name="  ")


def test_a_recipient_may_have_no_surname() -> None:
    recipient = make_recipient(last_name=None)

    assert str(recipient.full_name) == "Данил"


def test_a_recipient_renders_as_a_name_and_a_phone() -> None:
    assert str(make_recipient()) == "Данил Ковалев, +79991234567"


def test_a_recipient_is_built_positionally() -> None:
    """Mapped as a composite over three columns, which is rebuilt by position.

    Swapping two fields here would swap two columns silently, with nothing
    failing until somebody read a delivery back out.
    """
    recipient = Recipient("Данил", "Ковалев", make_phone_number())

    assert recipient.first_name == "Данил"
    assert recipient.last_name == "Ковалев"
    assert recipient.phone_number == make_phone_number()
