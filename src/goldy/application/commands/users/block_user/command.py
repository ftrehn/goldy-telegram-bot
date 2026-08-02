from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.user import UserView


@dataclass(frozen=True, slots=True)
class BlockUserCommand(Command[UserView]):
    """Bars a person from the shop, with the reason on the record.

    The reason is required: whoever lifts the block months later is rarely
    whoever imposed it.
    """

    user_id: UUID
    reason: str
