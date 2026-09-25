from abc import abstractmethod
from contextlib import AbstractAsyncContextManager
from typing import Protocol


class CatalogSyncLock(Protocol):
    """Makes sure at most one catalog pass runs at a time, across every process.

    Not an optimisation. Each pass finalises by its own batch id, so two passes
    overlapping — a retried ``sync_catalog`` landing on the next cron tick, two
    workers picking up two ticks, the seeder run beside a worker — sweep each
    other: the one that finishes first deactivates and deletes every row the
    other has just restamped, and those products vanish until the next pass.

    A try-lock rather than a wait. A pass that finds another one running has
    nothing to add — the running one will bring the same catalog — so it skips
    instead of queueing behind it and doing the whole job a second time.
    """

    @abstractmethod
    def hold(self) -> AbstractAsyncContextManager[bool]:
        """Tries to take the lock for the duration of the ``async with`` block.

        Yields ``True`` when this pass holds the lock and may run, ``False``
        when another pass holds it and this one must not. A lock taken is
        released when the block exits, however it exits.

        Raises:
            AppError: the lock could not be asked for at all — the adapter's
                own infrastructure error. No pass runs then.
        """
        raise NotImplementedError
