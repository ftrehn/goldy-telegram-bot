from collections.abc import Iterable

from dishka import Provider

from goldy.setup.ioc.providers import (
    bootstrap_handlers_provider,
    configs_provider,
    database_provider,
    domain_provider,
    gateways_provider,
    mappers_provider,
    mediator_provider,
    pipelines_provider,
    services_provider,
    user_handlers_provider,
)


def common_providers() -> Iterable[Provider]:
    """Everything that does not care which process it is running in.

    Split by concern rather than by layer: each function owns one kind of thing
    and states its own scope, so a lifetime mistake is visible in the file that
    made it instead of buried in one long list.

    Nothing here touches aiogram or taskiq, and nothing here needs to know who
    is acting. That is what lets the bot, the worker and — later — MAX share it
    without any of them being able to resolve something the others own.
    """
    return (
        configs_provider(),
        database_provider(),
        domain_provider(),
        mappers_provider(),
        gateways_provider(),
        pipelines_provider(),
        bootstrap_handlers_provider(),
        mediator_provider(),
    )


def interactive_providers() -> Iterable[Provider]:
    """What a process serving a person adds on top of the core.

    Everything here leads back to ``IdentityProvider``, which only exists while
    an update from a real account is being handled. Shared by Telegram and, in
    time, MAX — the two differ only in how they answer "who is writing".
    """
    return (
        services_provider(),
        user_handlers_provider(),
    )
