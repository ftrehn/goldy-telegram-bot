from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.orders.errors import (
    EmptyCancellationReasonError,
    TooLongCancellationReasonError,
)

MAX_CANCELLATION_REASON_LENGTH: Final[int] = 500


@dataclass(frozen=True, kw_only=True)
class CancellationReason(ValueObject):
    """Why an order was stopped.

    Kept apart from ``BlockReason`` even though both are short pieces of
    explanatory text: they are different concepts with different lifecycles,
    and merging them into one "reason" would make it impossible to constrain
    either one without constraining the other.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "Cancellation reason cannot be empty."
            raise EmptyCancellationReasonError(msg)

        if len(self.value) > MAX_CANCELLATION_REASON_LENGTH:
            msg = (
                f"Cancellation reason cannot be longer than "
                f"{MAX_CANCELLATION_REASON_LENGTH} characters, "
                f"got {len(self.value)}."
            )
            raise TooLongCancellationReasonError(msg)

    def __str__(self) -> str:
        return self.value
