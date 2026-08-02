from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

from goldy.domain.common.event import Event

if TYPE_CHECKING:
    from collections.abc import Iterable


class EventBus(Protocol):
    @abstractmethod
    async def publish(self, events: Iterable[Event]) -> None:
        raise NotImplementedError
