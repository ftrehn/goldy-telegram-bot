from typing import TYPE_CHECKING, Final, override

from dature import V, load

from goldy.domain.common.error import DomainError
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.infrastructure.adapters.auth.static_admin_registry import PHONE_SEPARATOR
from goldy.setup.bootstrap.loaders.loader import ConfigLoader
from goldy.setup.configs.admin_config import AdminConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

    from dature.validators.root import RootPredicate

    from goldy.setup.bootstrap.sources.source_factory import SourceFactory


def _every_number_parses(config: AdminConfig) -> bool:
    """Whether every listed number is one we could actually match a user by.

    Checked at startup rather than at first use: a typo here means an
    administrator silently never gets their role, and the person who typed it
    would have no reason to suspect the config.
    """
    for raw in config.phone_numbers.split(PHONE_SEPARATOR):
        if not raw.strip():
            continue
        try:
            PhoneNumber.from_raw(raw)
        except DomainError:
            return False

    return True


class AdminConfigLoader(ConfigLoader[AdminConfig]):
    """``dature``-backed loader for :class:`AdminConfig`."""

    def __init__(self, source_factory: SourceFactory) -> None:
        self._source_factory: Final[SourceFactory] = source_factory

    @override
    def load(self) -> AdminConfig:
        return load(
            self._source_factory.create(),
            schema=AdminConfig,
            root_validators=self._root_validators(),
        )

    @staticmethod
    def _root_validators() -> Iterable[RootPredicate]:
        return (
            V.root(
                _every_number_parses,
                error_message=(
                    "GOLDY_ADMIN_PHONE_NUMBERS must be a comma-separated list of "
                    "phone numbers"
                ),
            ),
        )
