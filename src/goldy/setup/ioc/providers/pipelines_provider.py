from typing import Final

from dishka import Provider, Scope

from goldy.application.pipelines.events_pipeline import EventsPipeline
from goldy.application.pipelines.transaction_pipeline import TransactionPipeline


def pipelines_provider() -> Provider:
    """Pipelines are per request: each wraps that request's own unit of work."""
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(source=TransactionPipeline)
    provider.provide(source=EventsPipeline)
    return provider
