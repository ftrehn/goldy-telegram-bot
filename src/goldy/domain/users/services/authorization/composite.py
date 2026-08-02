from typing import Final, override

from goldy.domain.users.services.authorization.base import (
    Permission,
    PermissionContext,
)


class AnyOf[PC: PermissionContext](Permission[PC]):
    """Satisfied when at least one of its permissions is.

    Empty means denied: a rule that permits nothing should refuse everything,
    not wave everything through.
    """

    def __init__(self, *permissions: Permission[PC]) -> None:
        self._permissions: Final[tuple[Permission[PC], ...]] = permissions

    @override
    def is_satisfied_by(self, context: PC) -> bool:
        return any(
            permission.is_satisfied_by(context) for permission in self._permissions
        )


class AllOf[PC: PermissionContext](Permission[PC]):
    """Satisfied only when every one of its permissions is."""

    def __init__(self, *permissions: Permission[PC]) -> None:
        self._permissions: Final[tuple[Permission[PC], ...]] = permissions

    @override
    def is_satisfied_by(self, context: PC) -> bool:
        return bool(self._permissions) and all(
            permission.is_satisfied_by(context) for permission in self._permissions
        )
