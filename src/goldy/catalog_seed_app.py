"""Catalog seeding entry point.

Run with::

    python -m goldy.catalog_seed_app --file fixtures/catalog.json

A fourth process rather than a flag on the bot, because filling the catalog is
not something a running bot should be able to do to itself: the job opens no
broker, serves nobody and exits. Until 1C is on the other end of the queue,
this is how the projection gets its contents.
"""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Final

from sqlalchemy.orm import clear_mappers

from goldy.setup.bootstrap.setups.catalog_setup import seed_catalog
from goldy.setup.bootstrap.setups.configs_setup import load_shared_configs
from goldy.setup.bootstrap.setups.database_setup import setup_map_tables
from goldy.setup.bootstrap.setups.logging_setup import configure_logging
from goldy.setup.configs.logging_config import LoggingConfig
from goldy.setup.ioc.containers import make_catalog_seed_container

logger: Final[logging.Logger] = logging.getLogger(__name__)


def parse_args() -> Path:
    """The snapshot to read, named on the command line.

    A required argument with no default. A seeder that reaches for some
    conventional path when told nothing would eventually be run in the wrong
    directory and quietly sweep the catalog down to whatever that file held.
    """
    parser = argparse.ArgumentParser(prog="goldy.catalog_seed_app")
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="JSON catalog snapshot to import",
    )
    path: Path = parser.parse_args().file
    return path


async def run(path: Path) -> None:
    """Builds the seeder's own container, fills the catalog, tears both down.

    ``setup_map_tables`` runs here as it does in every entry point, exactly
    once per process: the mappings are global to SQLAlchemy and configuring
    them twice raises.
    """
    configure_logging(LoggingConfig())

    configs = load_shared_configs()

    setup_map_tables()

    container = make_catalog_seed_container(configs.as_context())

    try:
        await seed_catalog(container, path)
    finally:
        await container.close()
        clear_mappers()


def main() -> None:
    try:
        asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        logger.info("catalog seeding was interrupted")


if __name__ == "__main__":
    main()
