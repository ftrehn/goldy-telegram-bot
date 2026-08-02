from collections.abc import Iterable
from typing import Final, final, override

from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import Message


@final
class ChatTypeFilter(BaseFilter):
    """Restricts a handler to certain kinds of chat.

    Private-only is the norm here: an order carries a phone number and a
    delivery address, and a group is the wrong place to print either.
    """

    def __init__(self, allowed_chat_types: Iterable[ChatType]) -> None:
        self._allowed_chat_types: Final[frozenset[ChatType]] = frozenset(
            allowed_chat_types,
        )

    @override
    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self._allowed_chat_types
