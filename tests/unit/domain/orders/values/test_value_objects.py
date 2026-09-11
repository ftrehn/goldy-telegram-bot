import pytest

from goldy.domain.orders.errors import (
    EmptyCancellationReasonError,
    EmptyDeliveryAddressError,
    EmptyOrderCommentError,
    EmptyOrderNumberError,
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


@pytest.mark.parametrize("value", ("1000", "1234567890"))
def test_an_order_number_is_four_to_ten_digits(value: str) -> None:
    """The sequence starts at 1000, so the lower bound is the first number issued."""
    assert OrderNumber(value=value).value == value


@pytest.mark.parametrize("value", ("999", "12345678901", "10a4", "№1043", "1 043"))
def test_a_number_that_is_not_plain_digits_is_refused(value: str) -> None:
    """Prefixes and padding are how presentation shows it, not what is stored."""
    with pytest.raises(InvalidOrderNumberFormatError):
        OrderNumber(value=value)


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
    value = "я" * MIN_DELIVERY_ADDRESS_LENGTH

    assert DeliveryAddress(value=value).value == value


def test_an_overlong_address_is_refused() -> None:
    with pytest.raises(TooLongDeliveryAddressError):
        DeliveryAddress(value="я" * (MAX_DELIVERY_ADDRESS_LENGTH + 1))


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
