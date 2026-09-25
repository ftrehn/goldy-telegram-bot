"""One pass of a catalog source: every batch in, and only then the sweeps.

The ordering is the whole point. Each import commits on its own, so a pass that
fails halfway leaves some batches imported — harmless, because an upsert
removes nothing. A finalisation after a partial pass is not harmless: it would
deactivate every product the missing pages held and delete their prices.
"""

import pytest

from goldy.application.commands.catalog.catalog_synchronizer import (
    CatalogSynchronizer,
)
from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.error import CatalogSnapshotError, CatalogSourceError
from tests.unit.factories.catalog_factories import (
    BATCH_ID,
    make_pass_batches,
    make_pass_scopes,
    make_product_row,
    make_snapshot,
)
from tests.unit.stubs.catalog import (
    CatalogCommandSender,
    RecordingCatalogProjectionDao,
    ScriptedCatalogSource,
    StubCatalogSyncLock,
)


async def test_every_batch_is_imported_before_the_declared_scopes_are_swept(
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    source = ScriptedCatalogSource(
        batch_id=BATCH_ID,
        scopes=make_pass_scopes(),
        batches=make_pass_batches(),
    )

    await CatalogSynchronizer(source, catalog_command_sender, catalog_sync_lock).run()

    kinds = [type(request).__name__ for request in catalog_command_sender.requests]
    assert kinds == ["ImportCatalogCommand"] * 4 + ["FinalizeCatalogImportCommand"] * 3
    assert catalog_command_sender.finalizations == [
        FinalizeCatalogImportCommand(batch_id=BATCH_ID, scope=scope)
        for scope in make_pass_scopes()
    ]


async def test_the_report_adds_up_the_whole_pass(
    projection_dao: RecordingCatalogProjectionDao,
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    projection_dao.swept = 2
    source = ScriptedCatalogSource(
        batch_id=BATCH_ID,
        scopes=make_pass_scopes(),
        batches=make_pass_batches(),
    )

    report = await CatalogSynchronizer(
        source, catalog_command_sender, catalog_sync_lock
    ).run()

    assert report is not None
    assert report.batch_id == BATCH_ID
    assert report.batches == 4
    assert report.accepted == 6
    assert report.discarded == 0
    assert report.swept == 6


async def test_a_scope_no_batch_mentioned_is_still_swept(
    projection_dao: RecordingCatalogProjectionDao,
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    """A pass in which nothing had stock still covers stock.

    Every stock row the projection holds is stale then, and skipping the sweep
    because no batch said "stock" would keep showing what the site no longer
    reports.
    """
    source = ScriptedCatalogSource(batch_id=BATCH_ID, scopes=make_pass_scopes())

    await CatalogSynchronizer(source, catalog_command_sender, catalog_sync_lock).run()

    assert [scope for scope, _ in projection_dao.finalized] == list(make_pass_scopes())


async def test_a_source_that_fails_midway_leaves_the_imports_and_sweeps_nothing(
    projection_dao: RecordingCatalogProjectionDao,
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    source = ScriptedCatalogSource(
        batch_id=BATCH_ID,
        scopes=make_pass_scopes(),
        batches=make_pass_batches(),
        failure=CatalogSourceError("the site timed out on page three"),
    )

    with pytest.raises(CatalogSourceError):
        await CatalogSynchronizer(source, catalog_command_sender, catalog_sync_lock).run()

    assert len(catalog_command_sender.imports) == 4
    assert catalog_command_sender.finalizations == []
    assert projection_dao.finalized == []


async def test_an_import_that_fails_stops_the_pass_before_any_sweep(
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    catalog_command_sender.fail_on_import = 2
    source = ScriptedCatalogSource(
        batch_id=BATCH_ID,
        scopes=make_pass_scopes(),
        batches=make_pass_batches(),
    )

    with pytest.raises(CatalogSnapshotError):
        await CatalogSynchronizer(source, catalog_command_sender, catalog_sync_lock).run()

    assert len(catalog_command_sender.imports) == 2
    assert catalog_command_sender.finalizations == []


async def test_a_batch_stamped_with_another_pass_is_refused_before_it_is_imported(
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    """Finalising by one batch id would sweep every row the stray batch restamped."""
    stray = make_snapshot(batch_id="another-pass", products=(make_product_row(9),))
    source = ScriptedCatalogSource(
        batch_id=BATCH_ID,
        scopes=make_pass_scopes(),
        batches=(*make_pass_batches()[:1], stray),
    )

    with pytest.raises(CatalogSnapshotError):
        await CatalogSynchronizer(source, catalog_command_sender, catalog_sync_lock).run()

    assert len(catalog_command_sender.imports) == 1
    assert catalog_command_sender.finalizations == []


async def test_a_pass_that_finds_another_running_skips_without_touching_anything(
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    """Running anyway would sweep the other pass's freshly restamped rows."""
    catalog_sync_lock.taken_elsewhere = True
    source = ScriptedCatalogSource(
        batch_id=BATCH_ID,
        scopes=make_pass_scopes(),
        batches=make_pass_batches(),
    )

    report = await CatalogSynchronizer(
        source, catalog_command_sender, catalog_sync_lock
    ).run()

    assert report is None
    assert catalog_command_sender.requests == []


async def test_the_whole_pass_runs_under_the_lock_and_gives_it_back(
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    source = ScriptedCatalogSource(
        batch_id=BATCH_ID,
        scopes=make_pass_scopes(),
        batches=make_pass_batches(),
    )

    await CatalogSynchronizer(source, catalog_command_sender, catalog_sync_lock).run()

    assert (catalog_sync_lock.acquisitions, catalog_sync_lock.releases) == (1, 1)
    assert not catalog_sync_lock.held


async def test_a_failed_pass_still_gives_the_lock_back(
    catalog_command_sender: CatalogCommandSender,
    catalog_sync_lock: StubCatalogSyncLock,
) -> None:
    """A lock kept after a failure would block every later pass."""
    source = ScriptedCatalogSource(
        batch_id=BATCH_ID,
        scopes=make_pass_scopes(),
        batches=make_pass_batches(),
        failure=CatalogSourceError("the site went away"),
    )

    with pytest.raises(CatalogSourceError):
        await CatalogSynchronizer(source, catalog_command_sender, catalog_sync_lock).run()

    assert catalog_sync_lock.releases == 1
    assert not catalog_sync_lock.held
