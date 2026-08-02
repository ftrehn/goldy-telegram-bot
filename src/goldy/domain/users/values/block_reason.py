from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.users.errors import EmptyBlockReasonError, TooLongBlockReasonError

MAX_BLOCK_REASON_LENGTH: Final[int] = 500


@dataclass(frozen=True, kw_only=True)
class BlockReason(ValueObject):
    """Why a person was blocked.

    Required rather than optional: whoever lifts the block months later is
    rarely whoever imposed it, and an unexplained block is one nobody dares
    undo.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "Block reason cannot be empty."
            raise EmptyBlockReasonError(msg)

        if len(self.value) > MAX_BLOCK_REASON_LENGTH:
            msg = (
                f"Block reason cannot be longer than "
                f"{MAX_BLOCK_REASON_LENGTH} characters, got {len(self.value)}."
            )
            raise TooLongBlockReasonError(msg)

    def __str__(self) -> str:
        return self.value
