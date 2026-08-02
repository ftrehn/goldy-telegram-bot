from enum import StrEnum


class UserStatus(StrEnum):
    """Whether the person may act in the shop at all."""

    ACTIVE = "active"
    BLOCKED = "blocked"
