"""Catalog receiver entry point.

Run with::

    python -m goldy.catalog_receiver_app

The fourth process, and the only one 1C writes to. A scheduled job in the
``ГолдиБот`` extension posts the catalog here in batches — categories,
products, price types, prices, stock, bindings — and waits for each answer
before sending the next one, so the order the projection needs is kept by the
sender and nothing here has to queue or reorder.

Not part of the bot, because the bot listens to people and nothing else: it
has no network port besides Telegram's long polling, and giving it one would
mean a secret for 1C living next to the bot token, in the process with the
largest surface. Not part of the worker either, because the worker consumes
queues and answers nobody; the receiver has to answer, synchronously, so that
1C can tell a committed batch from a dropped connection. A process that does
exactly one thing — accept a batch, run the command, reply — has one port, one
secret and one reason to restart.
"""

import asyncio
import logging
from typing import Final

from sqlalchemy.orm import clear_mappers

from goldy.setup.bootstrap.setups.catalog_receiver_setup import (
    serve_catalog_receiver,
)
from goldy.setup.bootstrap.setups.configs_setup import (
    load_catalog_receiver_config,
    load_shared_configs,
    make_catalog_receiver_container_context,
)
from goldy.setup.bootstrap.setups.database_setup import setup_map_tables
from goldy.setup.bootstrap.setups.logging_setup import configure_logging
from goldy.setup.configs.logging_config import LoggingConfig
from goldy.setup.ioc.containers import make_catalog_receiver_container

logger: Final[logging.Logger] = logging.getLogger(__name__)


async def run() -> None:
    """Builds the receiver's own container, serves until stopped, tears down.

    ``setup_map_tables`` runs here as it does in every entry point, exactly
    once per process: the mappings are global to SQLAlchemy and configuring
    them twice raises. The receiver's config is loaded beside the shared
    bundle rather than inside it, so the token 1C presents reaches this
    container and no other.
    """
    configure_logging(LoggingConfig())

    configs = load_shared_configs()
    receiver_config = load_catalog_receiver_config()

    setup_map_tables()

    container = make_catalog_receiver_container(
        make_catalog_receiver_container_context(configs, receiver_config),
    )

    try:
        await serve_catalog_receiver(container, receiver_config)
    finally:
        await container.close()
        clear_mappers()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt, SystemExit:
        logger.info("the catalog receiver was turned off")


if __name__ == "__main__":
    main()
