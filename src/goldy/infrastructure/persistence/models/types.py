from typing import Final, override

from sqlalchemy import Integer, String, Text, TypeDecorator
from sqlalchemy.engine import Dialect

from goldy.domain.catalog.values.product_name import ProductName
from goldy.domain.catalog.values.sku import Sku
from goldy.domain.catalog.values.source_id import SourceId
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.quantity import Quantity
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.cancellation_reason import CancellationReason
from goldy.domain.orders.values.delivery_address import DeliveryAddress
from goldy.domain.orders.values.order_comment import OrderComment
from goldy.domain.orders.values.order_number import OrderNumber
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.values.block_reason import BlockReason
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.locale import Locale
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.messenger_username import MessengerUsername
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus

MAX_PHONE_NUMBER_COLUMN_LENGTH = 20
MAX_EXTERNAL_ACCOUNT_ID_COLUMN_LENGTH = 64
MAX_MESSENGER_USERNAME_COLUMN_LENGTH = 64
MAX_ENUM_COLUMN_LENGTH = 20
MAX_LOCALE_COLUMN_LENGTH = 8
MAX_SOURCE_ID_COLUMN_LENGTH = 128
MAX_SKU_COLUMN_LENGTH = 64
MAX_PRODUCT_NAME_COLUMN_LENGTH = 255
MAX_UNIT_NAME_COLUMN_LENGTH = 32
MAX_CURRENCY_COLUMN_LENGTH = 8
MAX_ORDER_NUMBER_COLUMN_LENGTH = 16
MONEY_COLUMN_PRECISION = 14
MONEY_COLUMN_SCALE = 2
MEASURE_COLUMN_PRECISION = 14
MEASURE_COLUMN_SCALE = 3


class PhoneNumberType(TypeDecorator[PhoneNumber]):
    """Persists the E.164 number as plain text.

    Deliberately bypasses ``PhoneNumber.from_raw`` on the way back: rows are
    already canonical, and normalising on load would quietly repair data that
    should never have been stored malformed in the first place.
    """

    impl = String(MAX_PHONE_NUMBER_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: PhoneNumber | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> PhoneNumber | None:
        return PhoneNumber(value=value) if value is not None else None


class ExternalAccountIdType(TypeDecorator[ExternalAccountId]):
    """Persists a platform-issued account id as plain text."""

    impl = String(MAX_EXTERNAL_ACCOUNT_ID_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: ExternalAccountId | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> ExternalAccountId | None:
        return ExternalAccountId(value=value) if value is not None else None


class MessengerUsernameType(TypeDecorator[MessengerUsername]):
    """Persists the ``@handle`` as plain text; NULL when the account has none."""

    impl = String(MAX_MESSENGER_USERNAME_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: MessengerUsername | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> MessengerUsername | None:
        return MessengerUsername(value=value) if value is not None else None


class BlockReasonType(TypeDecorator[BlockReason]):
    """Persists the block reason as text; NULL while the person is active."""

    impl = Text
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: BlockReason | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> BlockReason | None:
        return BlockReason(value=value) if value is not None else None


class MessengerPlatformType(TypeDecorator[MessengerPlatform]):
    """Persists the platform as its ``StrEnum`` value.

    Text rather than a native database enum, so adding a platform is a code
    change and not a migration — which matters here, since MAX support is
    planned and further messengers are plausible.
    """

    impl = String(MAX_ENUM_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: MessengerPlatform | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> MessengerPlatform | None:
        return MessengerPlatform(value) if value is not None else None


class LocaleType(TypeDecorator[Locale]):
    """Persists the chosen language as its bare subtag.

    Rebuilding through the constructor rather than ``from_language_code``: a
    row holding a locale we no longer ship should fail loudly on load, not
    quietly become Russian and hide that a translation went missing.
    """

    impl = String(MAX_LOCALE_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: Locale | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> Locale | None:
        return Locale(value=value) if value is not None else None


class UserRoleType(TypeDecorator[UserRole]):
    """Persists the role as its ``StrEnum`` value."""

    impl = String(MAX_ENUM_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: UserRole | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> UserRole | None:
        return UserRole(value) if value is not None else None


class UserStatusType(TypeDecorator[UserStatus]):
    """Persists the status as its ``StrEnum`` value.

    Rebuilding the enum on load is what keeps ``user.is_active`` working on a
    loaded aggregate.
    """

    impl = String(MAX_ENUM_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: UserStatus | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> UserStatus | None:
        return UserStatus(value) if value is not None else None


class SourceIdType[TSourceId: SourceId](TypeDecorator[TSourceId]):
    """Persists any id 1C knows one of its own objects by, as plain text.

    One decorator for all three :class:`SourceId` subclasses rather than one
    decorator each, parameterised by the class to rebuild on the way back — the
    pattern ``ExternalAccountIdType`` follows, with the difference that the
    length rule is already stated once in the domain.

    ``source_id_type`` is stored under exactly the name of the constructor
    argument, and it has to stay that way. SQLAlchemy builds a type's cache key
    out of the constructor arguments it finds in ``__dict__``, so naming the
    attribute ``_source_id_type`` would leave two instances holding different
    classes sharing one cache key — after which a cached result processor hands
    back a ``CategoryId`` where a ``ProductId`` was stored, silently and only
    once the cache is warm.
    """

    impl = String(MAX_SOURCE_ID_COLUMN_LENGTH)
    cache_ok = True

    def __init__(self, source_id_type: type[TSourceId]) -> None:
        super().__init__()
        self.source_id_type: Final[type[TSourceId]] = source_id_type

    @override
    def process_bind_param(
        self,
        value: TSourceId | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> TSourceId | None:
        return self.source_id_type(value=value) if value is not None else None


class SkuType(TypeDecorator[Sku]):
    """Persists the article as plain text; NULL when 1C gave the product none.

    A missing article is NULL and never an empty string. The generated
    ``sku_normalized`` column is computed from this one, and an empty string
    would put a row into the trigram index that can only ever match nothing.
    """

    impl = String(MAX_SKU_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: Sku | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> Sku | None:
        return Sku(value=value) if value is not None else None


class ProductNameType(TypeDecorator[ProductName]):
    """Persists the product name kept in an order line snapshot."""

    impl = String(MAX_PRODUCT_NAME_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: ProductName | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> ProductName | None:
        return ProductName(value=value) if value is not None else None


class CurrencyType(TypeDecorator[Currency]):
    """Persists the currency as its ``StrEnum`` value.

    Needed because ``Money`` is a ``composite`` over an amount and a currency:
    the second column has to hand a ``Currency`` back for the value object to
    be rebuilt positionally. Plain text rather than a native database enum, for
    the reason ``MessengerPlatformType`` gives.
    """

    impl = String(MAX_CURRENCY_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: Currency | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> Currency | None:
        return Currency(value) if value is not None else None


class QuantityType(TypeDecorator[Quantity]):
    """Persists how many pieces are being bought, as a plain integer.

    An ``integer`` and not a ``numeric`` because the domain has no fractional
    quantity at all — that is what keeps ``Money.times`` exact. The check
    constraint beside every quantity column restates the "at least one" rule,
    because a row written by hand would otherwise load into a ``Quantity``
    that refuses to be built, far from whoever wrote it.
    """

    impl = Integer
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: Quantity | None,
        dialect: Dialect,
    ) -> int | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: int | None,
        dialect: Dialect,
    ) -> Quantity | None:
        return Quantity(value=value) if value is not None else None


class OrderNumberType(TypeDecorator[OrderNumber]):
    """Persists the human-readable order number as plain text.

    Text rather than an integer although a sequence produces it: the number is
    what a person reads out over the phone, the domain keeps it as digits only,
    and an integer column would invite arithmetic on something that is a label.
    """

    impl = String(MAX_ORDER_NUMBER_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: OrderNumber | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> OrderNumber | None:
        return OrderNumber(value=value) if value is not None else None


class OrderStatusType(TypeDecorator[OrderStatus]):
    """Persists the order status as its ``StrEnum`` value.

    Rebuilding the enum on load is what keeps the transition table usable on a
    loaded order: ``ALLOWED_ORDER_TRANSITIONS`` is keyed by the member, and a
    bare string matches none of those keys.
    """

    impl = String(MAX_ENUM_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: OrderStatus | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> OrderStatus | None:
        return OrderStatus(value) if value is not None else None


class DeliveryAddressType(TypeDecorator[DeliveryAddress]):
    """Persists the address the customer typed, as one piece of text."""

    impl = Text
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: DeliveryAddress | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> DeliveryAddress | None:
        return DeliveryAddress(value=value) if value is not None else None


class OrderCommentType(TypeDecorator[OrderComment]):
    """Persists what the customer asked for; NULL when they asked nothing.

    NULL rather than an empty string, because the domain models "no comment" as
    no ``OrderComment`` at all, and two spellings of the same thing end with
    only one of them being handled.
    """

    impl = Text
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: OrderComment | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> OrderComment | None:
        return OrderComment(value=value) if value is not None else None


class CancellationReasonType(TypeDecorator[CancellationReason]):
    """Persists why an order was stopped; NULL while it is still alive."""

    impl = Text
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: CancellationReason | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> CancellationReason | None:
        return CancellationReason(value=value) if value is not None else None


class CancellationInitiatorType(TypeDecorator[CancellationInitiator]):
    """Persists who stopped the order as its ``StrEnum`` value."""

    impl = String(MAX_ENUM_COLUMN_LENGTH)
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: CancellationInitiator | None,
        dialect: Dialect,
    ) -> str | None:
        return value.value if value is not None else None

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> CancellationInitiator | None:
        return CancellationInitiator(value) if value is not None else None
