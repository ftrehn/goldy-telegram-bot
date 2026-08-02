import logging
from collections.abc import Iterable, Sequence
from typing import Final, Self, final, override

from goldy.application.common.ports.admin_registry import AdminRegistry
from goldy.domain.users.values.phone_number import PhoneNumber

logger: Final[logging.Logger] = logging.getLogger(__name__)

PHONE_SEPARATOR: Final[str] = ","


@final
class StaticAdminRegistry(AdminRegistry):
    """A fixed list of administrator numbers, settled at startup.

    Takes numbers rather than a config object: the composition root reads the
    environment and hands the result here, so infrastructure never has to
    import ``setup``.
    """

    def __init__(self, phone_numbers: Iterable[PhoneNumber]) -> None:
        self._phone_numbers: Final[frozenset[PhoneNumber]] = frozenset(phone_numbers)
        logger.info("admins: %d number(s) configured", len(self._phone_numbers))

    @classmethod
    def from_raw(cls, raw: str) -> Self:
        """Parses a comma-separated list the way a registration would.

        Normalising matters: a number typed as ``8 (999) 123-45-67`` in the
        environment has to compare equal to one registered as ``+79991234567``,
        or the whole mechanism silently does nothing.
        """
        return cls(
            PhoneNumber.from_raw(entry)
            for entry in raw.split(PHONE_SEPARATOR)
            if entry.strip()
        )

    @override
    def is_admin(self, phone_number: PhoneNumber) -> bool:
        return phone_number in self._phone_numbers

    @override
    def phone_numbers(self) -> Sequence[PhoneNumber]:
        return tuple(self._phone_numbers)
