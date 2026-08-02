from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import UserView


@dataclass(frozen=True, slots=True)
class RenameUserCommand(Command[UserView]):
    """Corrects the name a person is addressed and delivered to.

    Carries ``user_id`` even for the self-service case so one command backs
    both it and a manager fixing a customer's typo; who may do which is the
    permission's business, not the command's.
    """

    user_id: UUID
    first_name: str
    last_name: str | None = None
