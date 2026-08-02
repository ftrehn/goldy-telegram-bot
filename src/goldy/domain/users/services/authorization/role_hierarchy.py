from collections.abc import Mapping
from typing import Final

from goldy.domain.users.values.user_role import UserRole

SUBORDINATE_ROLES: Final[Mapping[UserRole, frozenset[UserRole]]] = {
    UserRole.ADMIN: frozenset({UserRole.MANAGER, UserRole.CUSTOMER}),
    UserRole.MANAGER: frozenset({UserRole.CUSTOMER}),
    UserRole.CUSTOMER: frozenset(),
}
"""Who each role is allowed to act upon.

Two rules that would otherwise need their own checks fall straight out of this
table, because nobody is their own subordinate: an administrator cannot touch
another administrator, and nobody can block themselves.

``ADMIN`` appears in no one's set, so the role cannot be handed out through the
bot at all — the first administrators are seeded from configuration.
"""
