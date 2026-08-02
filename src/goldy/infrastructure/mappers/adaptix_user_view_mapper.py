"""Converters from the aggregate to its view, built once at import time.

Almost every field goes through a ``link_function`` because adaptix links
fields, not paths: ``P[User].full_name.first_name`` is rejected, so each value
object has to be unwrapped by a function of its own. ``id`` needs one too —
``UserId`` is a ``NewType``, which adaptix does not see through. Only the
timestamps line up unaided.
"""

from collections.abc import Callable
from typing import Final, final, override
from uuid import UUID

from adaptix import P
from adaptix.conversion import get_converter, link_function

from goldy.application.common.ports.mappers.user_view_mapper import UserViewMapper
from goldy.application.common.views.user import MessengerAccountView, UserView
from goldy.domain.users.entities.messenger_account import MessengerAccount
from goldy.domain.users.entities.user import User


def _account_platform_of(account: MessengerAccount) -> str:
    return account.platform.value


def _account_external_id_of(account: MessengerAccount) -> str:
    return account.external_id.value


def _account_username_of(account: MessengerAccount) -> str | None:
    return account.username.value if account.username is not None else None


_convert_account: Final[Callable[[MessengerAccount], MessengerAccountView]] = (
    get_converter(
        MessengerAccount,
        MessengerAccountView,
        recipe=[
            link_function(_account_platform_of, P[MessengerAccountView].platform),
            link_function(_account_external_id_of, P[MessengerAccountView].external_id),
            link_function(_account_username_of, P[MessengerAccountView].username),
        ],
    )
)


def _id_of(user: User) -> UUID:
    return user.id


def _phone_number_of(user: User) -> str:
    return user.phone_number.value


def _first_name_of(user: User) -> str:
    return user.full_name.first_name


def _last_name_of(user: User) -> str | None:
    return user.full_name.last_name


def _role_of(user: User) -> str:
    return user.role.value


def _status_of(user: User) -> str:
    return user.status.value


def _block_reason_of(user: User) -> str | None:
    return user.block_reason.value if user.block_reason is not None else None


def _notify_via_of(user: User) -> str:
    return user.preferences.notify_via.value


def _locale_of(user: User) -> str:
    return user.preferences.locale.value


def _marketing_consent_of(user: User) -> bool:
    return user.preferences.marketing_consent


def _accounts_of(user: User) -> tuple[MessengerAccountView, ...]:
    return tuple(_convert_account(account) for account in user.accounts)


_convert_user: Final[Callable[[User], UserView]] = get_converter(
    User,
    UserView,
    recipe=[
        link_function(_id_of, P[UserView].id),
        link_function(_phone_number_of, P[UserView].phone_number),
        link_function(_first_name_of, P[UserView].first_name),
        link_function(_last_name_of, P[UserView].last_name),
        link_function(_role_of, P[UserView].role),
        link_function(_status_of, P[UserView].status),
        link_function(_block_reason_of, P[UserView].block_reason),
        link_function(_notify_via_of, P[UserView].notify_via),
        link_function(_locale_of, P[UserView].locale),
        link_function(_marketing_consent_of, P[UserView].marketing_consent),
        link_function(_accounts_of, P[UserView].accounts),
    ],
)


@final
class AdaptixUserViewMapper(UserViewMapper):
    """Maps the aggregate to its view with an import-time converter.

    Module-level for the same reason as the other adaptix mappers: the retort
    caches the code it generates, so building the converter per instance would
    regenerate it on every command.
    """

    @override
    def to_view(self, user: User) -> UserView:
        return _convert_user(user)
