from collections.abc import Mapping
from typing import Final

from goldy.domain.users.values.user_role import UserRole

STAFF_ROLES: Final[frozenset[UserRole]] = frozenset({UserRole.MANAGER, UserRole.ADMIN})
"""Who works the shop rather than buys from it.

One statement of the rule, and every reader of it lives elsewhere: ``User``
answers ``is_staff`` from it, the staff filter of the bot reads the answer, and
the worker asks it who has to hear about a new order. A second spelling in any
of those places would drift from this one on the first change to roles.
"""

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
