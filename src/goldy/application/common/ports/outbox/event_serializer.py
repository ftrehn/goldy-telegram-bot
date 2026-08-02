from abc import abstractmethod
from typing import Protocol

from goldy.domain.common.event import Event

from application.common.ports.outbox.outbox_message import OutboxMessage


class EventSerializer(Protocol):
    """Port for converting domain events into serialised OutboxMessage DTOs."""

    @abstractmethod
    def serialize(self, event: Event) -> OutboxMessage:
        raise NotImplementedError