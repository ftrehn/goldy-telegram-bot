import logging
from typing import Final

from dishka import AsyncContainer, Scope

from goldy.application.commands.users.seed_admins.command import SeedAdminsCommand
from goldy.application.common.mediator.sender import Sender

logger: Final[logging.Logger] = logging.getLogger(__name__)


async def seed_admins(container: AsyncContainer) -> None:
    """Grants the configured numbers their role before the first update.

    Opens a request scope by hand: there is no update to hang one off, and the
    command still needs a session and a transaction like any other.

    Lives in bootstrap rather than in the entry point so the entry point stays
    an orchestration script — it is also the only place allowed to reach into
    ``application.commands``, which import-linter enforces.
    """
    async with container(scope=Scope.REQUEST) as request_container:
        sender = await request_container.get(Sender)
        response = await sender.send(SeedAdminsCommand())

    logger.info(
        "startup: admins granted=%d already=%d pending=%d",
        response.granted,
        response.already,
        response.pending,
    )
