from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, override

from goldy.domain.users.entities.user import User
from goldy.domain.users.services.authorization.base import (
    Permission,
    PermissionContext,
)
from goldy.domain.users.services.authorization.role_hierarchy import SUBORDINATE_ROLES
from goldy.domain.users.values.user_role import UserRole


@dataclass(frozen=True, kw_only=True)
class UserManagementContext(PermissionContext):
    """One person proposing to act upon another."""

    subject: User
    target: User


@dataclass(frozen=True, kw_only=True)
class RoleManagementContext(PermissionContext):
    """One person proposing to hand out a role."""

    subject: User
    target_role: UserRole


@dataclass(frozen=True, kw_only=True)
class StaffContext(PermissionContext):
    """One person proposing to look at the admin side."""

    subject: User


class IsStaff(Permission[StaffContext]):
    """Guards the admin side as a whole, before any per-target rule."""

    @override
    def is_satisfied_by(self, context: StaffContext) -> bool:
        return context.subject.is_staff


class CanManageSelf(Permission[UserManagementContext]):
    """Everyone may edit their own profile."""

    @override
    def is_satisfied_by(self, context: UserManagementContext) -> bool:
        return context.subject == context.target


class CanManageSubordinate(Permission[UserManagementContext]):
    """Satisfied when the target's role is below the subject's.

    Refuses equals, which is what stops an administrator from blocking a peer
    and, since nobody outranks themselves, from blocking themselves.
    """

    def __init__(
        self,
        role_hierarchy: Mapping[UserRole, frozenset[UserRole]] = SUBORDINATE_ROLES,
    ) -> None:
        self._role_hierarchy: Final[Mapping[UserRole, frozenset[UserRole]]] = (
            role_hierarchy
        )

    @override
    def is_satisfied_by(self, context: UserManagementContext) -> bool:
        allowed = self._role_hierarchy.get(context.subject.role, frozenset())
        return context.target.role in allowed


class CanManageRole(Permission[RoleManagementContext]):
    """Satisfied when the subject may hand out that particular role.

    Nobody may grant a role they do not outrank, so ``ADMIN`` — absent from
    every set — cannot be granted through the bot at all.
    """

    def __init__(
        self,
        role_hierarchy: Mapping[UserRole, frozenset[UserRole]] = SUBORDINATE_ROLES,
    ) -> None:
        self._role_hierarchy: Final[Mapping[UserRole, frozenset[UserRole]]] = (
            role_hierarchy
        )

    @override
    def is_satisfied_by(self, context: RoleManagementContext) -> bool:
        allowed = self._role_hierarchy.get(context.subject.role, frozenset())
        return context.target_role in allowed
