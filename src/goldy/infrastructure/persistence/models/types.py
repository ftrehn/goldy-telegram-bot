from typing import override

from sqlalchemy import String, Text, TypeDecorator
from sqlalchemy.engine import Dialect

from goldy.domain.users.values.block_reason import BlockReason
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.messenger_username import MessengerUsername
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus

MAX_PHONE_NUMBER_COLUMN_LENGTH = 20
MAX_EXTERNAL_ACCOUNT_ID_COLUMN_LENGTH = 64
MAX_MESSENGER_USERNAME_COLUMN_LENGTH = 64
MAX_ENUM_COLUMN_LENGTH = 20


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
