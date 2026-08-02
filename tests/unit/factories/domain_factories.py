"""Builders for the user domain objects the tests work with.

Every builder takes only the fields a test actually cares about and fills the
rest with valid defaults, so a test reads as the one thing it is varying.
"""

from collections import deque
from uuid import UUID

from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.entities.messenger_account import MessengerAccount
from goldy.domain.users.entities.user import User
from goldy.domain.users.registration import Registration
from goldy.domain.users.values.block_reason import BlockReason
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.full_name import FullName
from goldy.domain.users.values.locale import DEFAULT_LOCALE, Locale
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.messenger_username import MessengerUsername
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.domain.users.values.user_id import UserId
from goldy.domain.users.values.user_role import UserRole

CUSTOMER_PHONE: str = "+79991234567"
MANAGER_PHONE: str = "+79992222222"
ADMIN_PHONE: str = "+79993333333"

TELEGRAM_ACCOUNT_ID: str = "123456"
MAX_ACCOUNT_ID: str = "987654"


def make_user_id(value: str = "11111111-1111-1111-1111-111111111111") -> UserId:
    return UserId(UUID(value))


def make_events_collection() -> EventsCollection:
    return EventsCollection(events=deque())


def make_phone_number(value: str = CUSTOMER_PHONE) -> PhoneNumber:
    return PhoneNumber(value=value)


def make_external_account_id(value: str = TELEGRAM_ACCOUNT_ID) -> ExternalAccountId:
    return ExternalAccountId(value=value)


def make_full_name(
    first_name: str = "Данил", last_name: str | None = "Ковалев"
) -> FullName:
    return FullName(first_name=first_name, last_name=last_name)


def make_block_reason(value: str = "Оскорблял поддержку") -> BlockReason:
    return BlockReason(value=value)


def make_account(
    platform: MessengerPlatform = MessengerPlatform.TELEGRAM,
    external_id: str = TELEGRAM_ACCOUNT_ID,
    username: str | None = "c3equalz",
) -> MessengerAccount:
    return MessengerAccount(
        platform=platform,
        external_id=ExternalAccountId(value=external_id),
        username=MessengerUsername(value=username) if username is not None else None,
    )


def make_locale(value: str = DEFAULT_LOCALE) -> Locale:
    return Locale(value=value)


def make_registration(
    phone_number: str = CUSTOMER_PHONE,
    account: MessengerAccount | None = None,
    locale: str = DEFAULT_LOCALE,
) -> Registration:
    return Registration(
        phone_number=make_phone_number(phone_number),
        full_name=make_full_name(),
        account=account if account is not None else make_account(),
        locale=make_locale(locale),
    )


def make_registered_user(
    user_id: UserId | None = None,
    phone_number: str = CUSTOMER_PHONE,
    role: UserRole = UserRole.CUSTOMER,
    account: MessengerAccount | None = None,
    events_collection: EventsCollection | None = None,
) -> tuple[User, EventsCollection]:
    """A freshly registered user together with the collection they report to.

    The role is applied after registration because that is the only way it can
    happen in production too — everyone starts as a customer.
    """
    collection = (
        events_collection if events_collection is not None else make_events_collection()
    )
    user = User.register(
        user_id=user_id if user_id is not None else make_user_id(),
        events_collection=collection,
        registration=make_registration(phone_number=phone_number, account=account),
    )

    if role is not UserRole.CUSTOMER:
        user.assign_role(role)

    return user, collection


def make_customer(
    user_id: str = "11111111-1111-1111-1111-111111111111",
    phone_number: str = CUSTOMER_PHONE,
) -> User:
    user, _ = make_registered_user(
        user_id=make_user_id(user_id),
        phone_number=phone_number,
    )
    return user


def make_manager(
    user_id: str = "22222222-2222-2222-2222-222222222222",
) -> User:
    user, _ = make_registered_user(
        user_id=make_user_id(user_id),
        phone_number=MANAGER_PHONE,
        role=UserRole.MANAGER,
        account=make_account(external_id="222222"),
    )
    return user


def make_admin(
    user_id: str = "33333333-3333-3333-3333-333333333333",
) -> User:
    user, _ = make_registered_user(
        user_id=make_user_id(user_id),
        phone_number=ADMIN_PHONE,
        role=UserRole.ADMIN,
        account=make_account(external_id="333333"),
    )
    return user


def make_people_by_role() -> dict[UserRole, User]:
    """One person per role, so a rule can be checked against the whole matrix.

    Keyed by role because that is what the authorization rules read; a test
    then names the pair it is checking instead of assembling two users.
    """
    return {
        UserRole.CUSTOMER: make_customer(),
        UserRole.MANAGER: make_manager(),
        UserRole.ADMIN: make_admin(),
    }
