import asyncio
import logging
import signal
from typing import Final

from aiohttp import web
from dishka import AsyncContainer

from goldy.infrastructure.catalog_receiver.app import create_catalog_receiver_app
from goldy.setup.configs.catalog_receiver_config import CatalogReceiverConfig

logger: Final[logging.Logger] = logging.getLogger(__name__)

BYTES_PER_MIB: Final[int] = 1024 * 1024


def _stop_on_sigterm(stop: asyncio.Event) -> None:
    """Turns SIGTERM into the same orderly stop Ctrl+C gives.

    Docker stops a container with SIGTERM and follows up with SIGKILL ten
    seconds later. Left to the default disposition, SIGTERM ends the process
    at once, in the middle of whatever batch is being committed: 1C sees a
    dropped connection for a request that may or may not have gone through,
    and the runner never gets to close the container behind it. Setting the
    event instead lets ``serve_catalog_receiver`` fall through to its
    ``finally`` and drain the site first.

    Windows has no signal handlers on the event loop and says so with
    ``NotImplementedError``. There the process is stopped with Ctrl+C, which
    arrives as ``KeyboardInterrupt`` and takes the same ``finally`` path from
    the entry point.
    """
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, stop.set)
    except NotImplementedError:
        logger.debug("catalog_receiver: no SIGTERM handler on this platform")


async def serve_catalog_receiver(
    container: AsyncContainer,
    config: CatalogReceiverConfig,
) -> None:
    """Listens for 1C until told to stop, then lets what is in flight finish.

    A runner and a site by hand rather than ``web.run_app``, because that
    helper owns the event loop and the signal handling, and the entry point
    already owns both: it has a container to close and mappers to clear after
    the server is gone, in the order every other process does it. The runner
    gives the same graceful shutdown — stop accepting, wait for the handlers
    still running, fire the application's shutdown hooks — without taking the
    loop away.

    The body ceiling is passed in bytes because that is what aiohttp counts
    in; the config keeps mebibytes because that is what a person sets.

    Waiting on an event rather than sleeping forever is what makes SIGTERM a
    stop instead of a kill. ``KeyboardInterrupt`` and ``SystemExit`` do not
    set it — they cancel the task from outside — and land in the same
    ``finally``, so the site is torn down on every path out of here.
    """
    app: web.Application = create_catalog_receiver_app(
        container,
        token=config.token,
        max_body_bytes=config.max_body_mib * BYTES_PER_MIB,
    )
    runner = web.AppRunner(app)
    await runner.setup()

    try:
        site = web.TCPSite(runner, config.host, config.port)
        await site.start()
        logger.info(
            "catalog_receiver: listening on http://%s:%d",
            config.host,
            config.port,
        )

        stop = asyncio.Event()
        _stop_on_sigterm(stop)
        await stop.wait()
    finally:
        await runner.cleanup()
