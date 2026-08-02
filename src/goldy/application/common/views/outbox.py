from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RelayOutboxResponse:
    """Outcome of one relay tick, for the worker log."""

    published: int
    total: int
