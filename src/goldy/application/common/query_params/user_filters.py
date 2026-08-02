from dataclasses import dataclass

from goldy.domain.users.values.user_role import UserRole
from goldy.domain.users.values.user_status import UserStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class UserFilters:
    """Narrows the admin list. Every field unset means "everyone"."""

    role: UserRole | None = None
    status: UserStatus | None = None
    search: str | None = None
    """Matched against name and phone number."""
