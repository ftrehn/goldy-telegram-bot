from dataclasses import dataclass
from uuid import UUID

from goldy.domain.common.event import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRegistered(Event):
    """A new person joined, arriving from ``platform``."""

    user_id: UUID
    phone_number: str
    platform: str
    external_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MessengerAccountLinked(Event):
    """An existing person started writing from another platform too."""

    user_id: UUID
    platform: str
    external_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MessengerAccountUnlinked(Event):
    user_id: UUID
    platform: str
    external_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRenamed(Event):
    user_id: UUID
    old_full_name: str
    new_full_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UserPhoneNumberChanged(Event):
    user_id: UUID
    old_phone_number: str
    new_phone_number: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UserPreferencesChanged(Event):
    user_id: UUID
    notify_via: str
    locale: str
    marketing_consent: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRoleChanged(Event):
    user_id: UUID
    old_role: str
    new_role: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UserBlocked(Event):
    user_id: UUID
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UserUnblocked(Event):
    user_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SiteAccountLinked(Event):
    """The person linked themselves to their customer account on the site.

    Carries no name and no company: the event travels through the outbox and
    a queue, and whoever needs to know whom they linked to reads the user.
    """

    user_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class SiteAccountUnlinked(Event):
    """The link to the site's customer account is gone, on either side's word."""

    user_id: UUID
