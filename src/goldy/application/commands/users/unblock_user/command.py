from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import UserView


@dataclass(frozen=True, slots=True)
class UnblockUserCommand(Command[UserView]):
    """Lets a blocked person back into the shop."""

    user_id: UUID
