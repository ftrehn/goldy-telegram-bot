"""What every catalog document read with adaptix needs, whoever sent it.

Shared by the snapshot mapper the seeder's file goes through and the site
catalog documents the worker pulls: both read numbers that become prices, and
both owe whoever reads the log a path to the field that was wrong.
"""

from collections.abc import Iterator
from decimal import Decimal, InvalidOperation

from adaptix.load_error import AggregateLoadError, ValueLoadError
from adaptix.struct_trail import get_trail


def decimal_through_text(value: object) -> Decimal:
    """A number read through its text, so no binary float reaches a price."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        msg = "Expected a number."
        raise ValueLoadError(msg, value)

    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        msg = "Expected a number."
        raise ValueLoadError(msg, value) from exc


def load_error_reasons(
    exc: BaseException,
    subject: str,
    root: str = "",
) -> Iterator[str]:
    """Every refusal in the tree adaptix raised, each with the path it names.

    adaptix reports a model with two bad fields as one aggregate holding two
    errors, and each error carries the trail from its parent. Flattened, the
    log says ``products[7].name: expected a string`` and whoever reads it
    fixes the export instead of guessing at it. *subject* names the document
    itself, for a refusal that has no path at all; *root* prefixes every path,
    for a document that is a bare list and would otherwise read ``[7].name``.
    """
    yield from _leaves(exc, root, subject)


def _leaves(exc: BaseException, trail: str, subject: str) -> Iterator[str]:
    path = trail + "".join(
        f"[{segment}]" if isinstance(segment, int) else f".{segment}"
        for segment in get_trail(exc)
    )

    if isinstance(exc, AggregateLoadError):
        for inner in exc.exceptions:
            yield from _leaves(inner, path, subject)
        return

    yield f"{path.lstrip('.') or subject}: {exc}"
