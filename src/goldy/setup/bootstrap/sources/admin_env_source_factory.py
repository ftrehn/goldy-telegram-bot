from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.admin_config import AdminConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class AdminEnvSourceFactory(SourceFactory):
    """Maps ``GOLDY_ADMIN_*`` environment variables onto :class:`AdminConfig`."""

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[AdminConfig].phone_numbers: "GOLDY_ADMIN_PHONE_NUMBERS",
            },
        )
