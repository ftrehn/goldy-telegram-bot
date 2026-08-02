from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Self, final

from goldy.domain.common.aggregate import Aggregate
from goldy.domain.users.entities.messenger_account import MessengerAccount
from goldy.domain.users.errors import (
    LastMessengerAccountError,
    MessengerAccountNotLinkedError,
    NotificationTargetNotLinkedError,
    PlatformAlreadyLinkedError,
    UserAlreadyBlockedError,
    UserIsBlockedError,
    UserNotBlockedError,
)
from goldy.domain.users.events import (
    MessengerAccountLinked,
    MessengerAccountUnlinked,
    UserBlocked,
    UserPhoneNumberChanged,
    UserPreferencesChanged,
    UserRegistered,
    UserRenamed,
    UserRoleChanged,
    UserUnblocked,
)
from goldy.domain.users.values.block_reason import BlockReason
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.full_name import FullName
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.messenger_username import MessengerUsername
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.domain.users.values.user_id import UserId
from goldy.domain.users.values.user_preferences import UserPreferences
from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus

if TYPE_CHECKING:
    from goldy.domain.common.event import Event
    from goldy.domain.common.events_collection import EventsCollection

_STAFF_ROLES: frozenset[UserRole] = frozenset({UserRole.MANAGER, UserRole.ADMIN})


@final
@dataclass(eq=False, kw_only=True)
class User(Aggregate[UserId]):
    """A person who uses the bot, whichever messenger they write from.

    The aggregate is the human, not the messenger account: someone writing from
    Telegram today and MAX tomorrow is one ``User`` with two accounts, one
    order history and one phone number. See ADR-0001 for why.

    Everything the aggregate can decide by looking at its own fields it decides
    itself — linking platforms, blocking, editing the profile. Deciding *who is
    allowed* to do those things needs a second person and lives in
    ``AccessService``; minting a new identifier needs a generator and lives in
    ``UserFactory``.

    Two rules cannot be enforced here at all — that a phone number belongs to
    exactly one user, and that a messenger account does too. Both span
    aggregates, and any check by reading loses to a concurrent registration, so
    unique indexes hold them and the handler retries on conflict.
    """

    phone_number: PhoneNumber
    full_name: FullName
    preferences: UserPreferences
    role: UserRole = field(default=UserRole.CUSTOMER)
    status: UserStatus = field(default=UserStatus.ACTIVE)
    block_reason: BlockReason | None = field(default=None)
    accounts: list[MessengerAccount] = field(default_factory=list)

    @classmethod
    def register(
        cls,
        *,
        user_id: UserId,
        events_collection: EventsCollection,
        phone_number: PhoneNumber,
        full_name: FullName,
        account: MessengerAccount,
    ) -> Self:
        """Creates a person together with the account they arrived from.

        There is no separate "create, then link" step: a user with no account
        is unreachable, and letting that state exist even for an instant means
        every later reader has to cope with it.

        Notifications default to the platform they came from — the only one we
        know reaches them.
        """
        user = cls(
            id=user_id,
            events_collection=events_collection,
            phone_number=phone_number,
            full_name=full_name,
            preferences=UserPreferences(notify_via=account.platform),
            accounts=[account],
        )
        user.events_collection.add_event(
            UserRegistered(
                user_id=user_id,
                phone_number=str(phone_number),
                platform=account.platform.value,
                external_id=str(account.external_id),
            ),
        )
        return user

    def link_account(self, account: MessengerAccount) -> None:
        """Attaches another platform to this person.

        Idempotent for the account already attached: a repeated ``/start`` is
        not a business fact, so the handle is refreshed and no event is raised.

        Raises:
            PlatformAlreadyLinkedError: a *different* account of that platform
                is already attached.
        """
        linked = self.account_for(account.platform)

        if linked is not None:
            if linked.external_id == account.external_id:
                linked.username = account.username
                return

            msg = (
                f"User '{self.id}' already has a {account.platform.value} account "
                f"('{linked.external_id}')."
            )
            raise PlatformAlreadyLinkedError(msg)

        self.accounts.append(account)
        self._touch()
        self._record(
            MessengerAccountLinked(
                user_id=self.id,
                platform=account.platform.value,
                external_id=str(account.external_id),
            ),
        )

    def unlink_account(self, platform: MessengerPlatform) -> None:
        """Detaches a platform.

        If it was the notification target, notifications move to a platform
        that remains — leaving them pointed at nothing would make the aggregate
        invalid the moment it is saved.

        Raises:
            MessengerAccountNotLinkedError: nothing is attached for ``platform``.
            LastMessengerAccountError: it is the only account left, and
                detaching it would leave the person unreachable.
        """
        account = self.account_for(platform)

        if account is None:
            msg = f"User '{self.id}' has no {platform.value} account."
            raise MessengerAccountNotLinkedError(msg)

        if len(self.accounts) == 1:
            msg = (
                f"Cannot unlink the last account of user '{self.id}' — "
                f"they would become unreachable."
            )
            raise LastMessengerAccountError(msg)

        self.accounts.remove(account)

        if self.preferences.notify_via == platform:
            self.preferences = self.preferences.with_notify_via(
                self.accounts[0].platform,
            )

        self._touch()
        self._record(
            MessengerAccountUnlinked(
                user_id=self.id,
                platform=platform.value,
                external_id=str(account.external_id),
            ),
        )

    def refresh_username(
        self,
        platform: MessengerPlatform,
        username: MessengerUsername | None,
    ) -> None:
        """Stores the handle seen on the latest update.

        Raises no event and does not bump ``updated_at``: the platform changed
        it, the person did nothing, and nothing downstream cares.
        """
        account = self.account_for(platform)

        if account is not None:
            account.username = username

    def rename(self, full_name: FullName) -> None:
        if full_name == self.full_name:
            return

        old_full_name = self.full_name
        self.full_name = full_name
        self._touch()
        self._record(
            UserRenamed(
                user_id=self.id,
                old_full_name=str(old_full_name),
                new_full_name=str(full_name),
            ),
        )

    def change_phone_number(self, phone_number: PhoneNumber) -> None:
        """Moves the person to another number.

        Whether that number is free is not decided here — it is a fact about
        every other user, which this aggregate cannot see.
        """
        if phone_number == self.phone_number:
            return

        old_phone_number = self.phone_number
        self.phone_number = phone_number
        self._touch()
        self._record(
            UserPhoneNumberChanged(
                user_id=self.id,
                old_phone_number=str(old_phone_number),
                new_phone_number=str(phone_number),
            ),
        )

    def change_preferences(self, preferences: UserPreferences) -> None:
        """Replaces the notification settings.

        Raises:
            NotificationTargetNotLinkedError: notifications would be pointed at
                a platform this person does not use.
        """
        if self.account_for(preferences.notify_via) is None:
            msg = (
                f"User '{self.id}' has no {preferences.notify_via.value} account "
                f"to be notified through."
            )
            raise NotificationTargetNotLinkedError(msg)

        if preferences == self.preferences:
            return

        self.preferences = preferences
        self._touch()
        self._record(
            UserPreferencesChanged(
                user_id=self.id,
                notify_via=preferences.notify_via.value,
                marketing_consent=preferences.marketing_consent,
            ),
        )

    def assign_role(self, role: UserRole) -> None:
        """Puts the person in a role.

        Says nothing about who may do this — the aggregate cannot see the actor.
        ``AccessService`` answers that before this is called.
        """
        if role == self.role:
            return

        old_role = self.role
        self.role = role
        self._touch()
        self._record(
            UserRoleChanged(
                user_id=self.id,
                old_role=old_role.value,
                new_role=role.value,
            ),
        )

    def block(self, reason: BlockReason) -> None:
        """Bars the person from acting.

        Raises:
            UserAlreadyBlockedError: they are already blocked, and overwriting
                the reason would erase why.
        """
        if self.status is UserStatus.BLOCKED:
            msg = f"User '{self.id}' is already blocked."
            raise UserAlreadyBlockedError(msg)

        self.status = UserStatus.BLOCKED
        self.block_reason = reason
        self._touch()
        self._record(UserBlocked(user_id=self.id, reason=str(reason)))

    def unblock(self) -> None:
        """Lets the person act again.

        Raises:
            UserNotBlockedError: they were not blocked to begin with.
        """
        if self.status is UserStatus.ACTIVE:
            msg = f"User '{self.id}' is not blocked."
            raise UserNotBlockedError(msg)

        self.status = UserStatus.ACTIVE
        self.block_reason = None
        self._touch()
        self._record(UserUnblocked(user_id=self.id))

    def ensure_active(self) -> None:
        """Guards anything a blocked person must not do.

        Raises:
            UserIsBlockedError: they are blocked.
        """
        if self.status is not UserStatus.ACTIVE:
            msg = f"User '{self.id}' is blocked and cannot act."
            raise UserIsBlockedError(msg)

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE

    @property
    def is_staff(self) -> bool:
        """Whether this person may reach the admin side at all."""
        return self.role in _STAFF_ROLES

    def account_for(self, platform: MessengerPlatform) -> MessengerAccount | None:
        return next(
            (account for account in self.accounts if account.platform is platform),
            None,
        )

    def has_account(
        self,
        platform: MessengerPlatform,
        external_id: ExternalAccountId,
    ) -> bool:
        account = self.account_for(platform)
        return account is not None and account.external_id == external_id

    def notification_account(self) -> MessengerAccount:
        """The account to deliver notifications to.

        Raises:
            NotificationTargetNotLinkedError: the chosen platform is no longer
                attached, which should be unreachable — ``unlink_account`` and
                ``change_preferences`` both keep the two in step.
        """
        account = self.account_for(self.preferences.notify_via)

        if account is None:
            msg = (
                f"User '{self.id}' is set to be notified via "
                f"{self.preferences.notify_via.value}, which is not linked."
            )
            raise NotificationTargetNotLinkedError(msg)

        return account

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    def _record(self, event: Event) -> None:
        self.events_collection.add_event(event)
