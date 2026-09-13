"""The snapshot mapper, built on one private retort at import time.

adaptix reads the contract straight off the dataclasses in
``application.common.ports.catalog.catalog_snapshot``: a required field, an
optional one, a tuple of rows, an enum by its value — every rule the old
hand-written reader restated is the annotation itself. What the recipe adds is
the two things JSON gets wrong for us: a number has to reach ``Decimal`` through
its text so ``0.1`` stays one tenth, and a blank string is refused everywhere,
because an identifier or a name that is ``""`` is a broken export and never a
value.

The retort is private and ``Final`` at module level, never built in a
constructor: it caches the loaders it generates, and a retort per instance
would regenerate them on every read and keep the cache for nothing.
"""

from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Final, final, override

from adaptix import Retort, loader
from adaptix.load_error import AggregateLoadError, LoadError, ValueLoadError
from adaptix.struct_trail import get_trail

from goldy.application.common.ports.catalog import CatalogSnapshot
from goldy.infrastructure.adapters.catalog.catalog_snapshot_mapper import (
    CatalogSnapshotMapper,
)
from goldy.infrastructure.errors import CatalogSourceReadError


def _decimal_through_text(value: object) -> Decimal:
    """A number read through its text, so no binary float reaches a price."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        msg = "Expected a number."
        raise ValueLoadError(msg, value)

    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        msg = "Expected a number."
        raise ValueLoadError(msg, value) from exc


def _non_blank_text(value: object) -> str:
    """Text that says something, or a refusal — present and blank is not absent."""
    if not isinstance(value, str):
        msg = "Expected a string."
        raise ValueLoadError(msg, value)

    if not value.strip():
        msg = "Expected a non-empty string."
        raise ValueLoadError(msg, value)

    return value


_retort: Final[Retort] = Retort(
    recipe=[
        loader(Decimal, _decimal_through_text),
        loader(str, _non_blank_text),
    ],
)


@final
class AdaptixCatalogSnapshotMapper(CatalogSnapshotMapper):
    """Reads a snapshot off a decoded JSON document with the retort above."""

    @override
    def to_snapshot(self, document: object) -> CatalogSnapshot:
        try:
            return _retort.load(document, CatalogSnapshot)
        except LoadError as exc:
            reasons = "; ".join(_leaves(exc))
            msg = f"The catalog snapshot is not shaped like one: {reasons}."
            raise CatalogSourceReadError(msg) from exc


def _leaves(exc: BaseException, trail: str = "") -> Iterator[str]:
    """Every refusal in the tree adaptix raised, each with the path it names.

    adaptix reports a model with two bad fields as one aggregate holding two
    errors, and each error carries the trail from its parent. Flattened, the
    seeder prints ``products[7].name: expected a string`` and whoever runs it
    fixes the fixture instead of guessing at it.
    """
    path = trail + "".join(
        f"[{segment}]" if isinstance(segment, int) else f".{segment}"
        for segment in get_trail(exc)
    )

    if isinstance(exc, AggregateLoadError):
        for inner in exc.exceptions:
            yield from _leaves(inner, path)
        return

    yield f"{path.lstrip('.') or 'the snapshot'}: {exc}"
