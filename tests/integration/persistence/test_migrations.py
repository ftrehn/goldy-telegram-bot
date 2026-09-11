"""The migrations against the mappers, on a database built only by them.

Two separate failures are worth catching here, and neither shows up anywhere
else. A revision chain that has grown a second head applies whichever branch
alembic happens to reach, so the schema depends on the order somebody merged
in. And a mapper edited without a migration beside it leaves the repository
describing a schema no deployment has — the tests still pass, because every
other test builds its database from these same migrations, and the first thing
to notice is production.

``compare_metadata`` is the same comparison ``alembic revision --autogenerate``
runs. Asking it for an empty answer is the "the diff should be empty" check
``AGENTS.md`` names, run automatically rather than by hand before a deploy.
"""

from pathlib import Path
from typing import Final

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine

from goldy.infrastructure.persistence.models.base import metadata

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
]


async def test_an_empty_database_ends_up_at_the_one_head(
    migrated_database: AsyncEngine,
) -> None:
    """Also the assertion that the revisions form a single chain.

    ``get_current_head`` refuses to answer when there are several, so a branch
    somebody forgot to merge fails here rather than on the deployment that
    applied only half of it.
    """
    head = ScriptDirectory.from_config(
        Config(str(PROJECT_ROOT / "alembic.ini")),
    ).get_current_head()

    async with migrated_database.connect() as connection:
        stamped = (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()

    assert stamped == head


async def test_the_migrated_schema_matches_the_mappers(
    migrated_database: AsyncEngine,
) -> None:
    """An empty diff, which is what tells the repository from the database."""
    async with migrated_database.connect() as connection:
        differences = await connection.run_sync(_differences)

    assert differences == []


def _differences(connection: Connection) -> list[object]:
    """What autogenerate would write if somebody asked for a revision now.

    Synchronous because alembic is, which is why it is handed to ``run_sync``
    rather than awaited — the same move ``migrations/env.py`` makes.
    """
    context = MigrationContext.configure(connection)
    return list(compare_metadata(context, metadata))
