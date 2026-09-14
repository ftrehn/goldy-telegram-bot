from typing import TYPE_CHECKING, override

from dature import EnvSource, F

from goldy.setup.bootstrap.sources.source_factory import SourceFactory
from goldy.setup.configs.catalog_receiver_config import CatalogReceiverConfig

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol


class CatalogReceiverEnvSourceFactory(SourceFactory):
    """Maps ``GOLDY_CATALOG_RECEIVER_*`` variables onto :class:`CatalogReceiverConfig`.

    The prefix is long on purpose. A receiver is the kind of thing whose
    settings are called ``HOST`` and ``PORT`` and ``TOKEN`` in every example,
    and bare names like those pick up whatever the environment already holds
    for somebody else — a ``PORT`` set by a platform, a ``TOKEN`` meant for the
    bot. Naming the process in the variable is what keeps 1C's token and the
    bot's from ever being the same one by accident.
    """

    @override
    def create(self) -> SourceProtocol:
        return EnvSource(
            field_mapping={
                F[CatalogReceiverConfig].host: "GOLDY_CATALOG_RECEIVER_HOST",
                F[CatalogReceiverConfig].port: "GOLDY_CATALOG_RECEIVER_PORT",
                F[CatalogReceiverConfig].token: "GOLDY_CATALOG_RECEIVER_TOKEN",
                F[CatalogReceiverConfig].max_body_mib: (
                    "GOLDY_CATALOG_RECEIVER_MAX_BODY_MIB"
                ),
            },
        )
