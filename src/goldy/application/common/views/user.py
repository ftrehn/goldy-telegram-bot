from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus


@dataclass(frozen=True, slots=True)
class MessengerAccountView:
    """One linked platform, flattened for presentation."""

    platform: str
    external_id: str
    username: str | None
    linked_at: datetime


@dataclass(frozen=True, slots=True)
class UserView:
    """A user as the bot and the admin side display them.

    Primitives rather than value objects: this crosses out of the domain, and
    handing a ``PhoneNumber`` to a keyboard renderer would let presentation
    depend on domain internals it has no business knowing.
    """

    id: UUID
    phone_number: str
    first_name: str
    last_name: str | None
    role: str
    status: str
    block_reason: str | None
    notify_via: str
    locale: str
    marketing_consent: bool
    accounts: tuple[MessengerAccountView, ...]
    created_at: datetime
    updated_at: datetime

    @property
    def is_blocked(self) -> bool:
        """Derived rather than stored, so it cannot disagree with ``status``."""
        return self.status == UserStatus.BLOCKED.value

    @property
    def is_staff(self) -> bool:
        """Whether this person may reach the admin side at all."""
        return self.role in {UserRole.MANAGER.value, UserRole.ADMIN.value}


@dataclass(frozen=True, slots=True)
class UserListView:
    """One page of users, with the count the pager needs."""

    users: tuple[UserView, ...]
    total: int


@dataclass(frozen=True, slots=True)
class SeedAdminsResponse:
    """Outcome of one seeding pass, for the startup log.

    ``pending`` counts numbers on the list that belong to nobody yet — normal
    on a fresh deployment, and worth seeing if it stays non-zero.
    """

    granted: int
    already: int
    pending: int
