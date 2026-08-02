from collections.abc import Sequence
from typing import Final, final, override

from goldy.application.common.ports.admin_registry import AdminRegistry
from goldy.domain.users.values.phone_number import PhoneNumber


@final
class StubAdminRegistry(AdminRegistry):
    """Says which numbers are administrators, without an environment to read."""

    def __init__(self, *raw_phone_numbers: str) -> None:
        self._phone_numbers: Final[frozenset[PhoneNumber]] = frozenset(
            PhoneNumber.from_raw(raw) for raw in raw_phone_numbers
        )

    @override
    def is_admin(self, phone_number: PhoneNumber) -> bool:
        return phone_number in self._phone_numbers

    @override
    def phone_numbers(self) -> Sequence[PhoneNumber]:
        return tuple(self._phone_numbers)
