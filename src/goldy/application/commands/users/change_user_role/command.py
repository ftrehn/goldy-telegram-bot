from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import UserView
from goldy.domain.users.values.user_role import UserRole


@dataclass(frozen=True, slots=True)
class ChangeUserRoleCommand(Command[UserView]):
    """Moves a person to another role.

    ``ADMIN`` cannot be granted through this command whoever asks — the role
    sits above everyone in the hierarchy, so no subject may hand it out. The
    first administrators are seeded from configuration instead.
    """

    user_id: UUID
    role: UserRole
