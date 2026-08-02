from collections.abc import Iterable
from typing import Final

from dishka import AsyncContainer, Provider, make_async_container
from dishka.integrations.taskiq import TaskiqProvider

from goldy.setup.ioc.containers.common import common_providers
from goldy.setup.ioc.providers import outbox_handlers_provider, task_manager_provider


def worker_providers() -> Iterable[Provider]:
    """The shared core plus the broker side of the world.

    No ``IdentityProvider`` here, and that is deliberate: a background task is
    nobody's request. A handler that needed one would fail to resolve at
    startup rather than halfway through a task, which is the whole reason the
    containers are assembled separately.
    """
    return (
        *common_providers(),
        task_manager_provider(),
        outbox_handlers_provider(),
        TaskiqProvider(),
    )


def make_worker_container(context: dict[type, object]) -> AsyncContainer:
    """Builds the container the taskiq worker and scheduler run on."""
    providers: Final[Iterable[Provider]] = tuple(worker_providers())
    return make_async_container(*providers, context=context)
