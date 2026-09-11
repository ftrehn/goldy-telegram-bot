"""Thirty lines that catch the failure only a customer would otherwise find.

A missing Fluent key fails at render time and nowhere else: nothing imports it,
no type checker follows it, and the first sign of trouble is a person halfway
through checkout receiving the word ``checkout-confirm``.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import pytest
from aiogram_i18n.cores import BaseCore
from fluent.runtime import FluentBundle

from goldy.domain.users.values.locale import SUPPORTED_LOCALES
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.locales_path import LOCALES_PATH
from goldy.presentation.telegram.handlers.errors import ERROR_TEXTS

LOCALES: Final[tuple[str, ...]] = tuple(sorted(SUPPORTED_LOCALES))

MESSAGE_DEFINITION: Final[re.Pattern[str]] = re.compile(
    r"^([a-zA-Z][a-zA-Z0-9_-]*) *=",
)
"""A message definition starts at column zero; a continuation is indented."""

MESSAGE_REFERENCE: Final[re.Pattern[str]] = re.compile(
    r"\{ *([a-zA-Z][a-zA-Z0-9_-]*) *\}",
)
"""One message embedded in another, which is a use as good as a declared key.

Nothing else can match: a variable carries a ``$``, a term a ``-``, and a
function is followed by its bracket rather than by the closing brace.
"""

_UNKNOWN_EXTERNAL: Final[str] = "Unknown external: "
"""How ``fluent.runtime`` words a missing argument, as opposed to a missing key.

Both arrive as ``FluentReferenceError``, so the wording is the only thing
separating "the caller did not pass ``$sku``" from "this file references a
message that does not exist" — and only the second is a defect in the
translations themselves.
"""


def declared_keys() -> tuple[str, ...]:
    """Every key the presentation layer will ever ask for."""
    return tuple(
        sorted(
            value
            for name, value in vars(text_keys).items()
            if name.isupper() and isinstance(value, str)
        ),
    )


@pytest.mark.parametrize("locale", LOCALES)
def test_every_declared_key_has_a_message(
    locale: str,
    i18n_core: BaseCore[Any],
) -> None:
    bundle = i18n_core.get_translator(locale)

    missing = [key for key in declared_keys() if not _has_message(bundle, key)]

    assert missing == []


@pytest.mark.parametrize("locale", LOCALES)
def test_refusals_render_without_any_arguments(
    locale: str,
    i18n_core: BaseCore[Any],
) -> None:
    """Because ``handle_app_error`` has nothing to pass them.

    It calls ``i18n.get(key)`` with no arguments, and a placeholder left in
    one of these messages does **not** reach the person as ``{ $max }``:
    ``FluentRuntimeCore.get`` raises ``FluentMessageError`` on an unknown
    external. So the cost of a placeholder here is not an ugly refusal, it is
    no refusal at all — the error handler itself dies, and the person who
    typed a quantity of zero is answered with silence.
    """
    for key in sorted(set(ERROR_TEXTS.values())):
        assert i18n_core.get(key, locale).strip()


@pytest.mark.parametrize("locale", LOCALES)
def test_no_key_is_defined_in_two_files(locale: str) -> None:
    """The bundle keeps the first definition and says nothing about the second.

    With the keys split over six files per language, two screens claiming
    ``order-status`` is theirs is an ordinary mistake, and its symptom is one
    screen quietly showing the other one's wording.
    """
    owners: dict[str, str] = {}
    duplicates: list[str] = []

    for path in _locale_files(locale):
        for key in _keys_in(path):
            if key in owners:
                duplicates.append(f"{key}: {owners[key]} and {path.name}")
            owners[key] = path.name

    assert duplicates == []


@pytest.mark.parametrize("locale", LOCALES)
def test_every_message_written_in_a_file_is_one_the_bundle_holds(
    locale: str,
    i18n_core: BaseCore[Any],
) -> None:
    """A message Fluent cannot parse is dropped, silently and one at a time.

    The parser turns a malformed entry into ``Junk`` — a selector with no
    ``*[other]`` branch, an unclosed placeable, a variant indented one space
    short — and the bundle is then built from everything *else* in the file.
    Nothing is logged, the other messages still work, and the key simply does
    not exist any more: the screen that asks for it dies with
    ``KeyNotFoundError``.

    Comparing the file against the bundle is what separates that from an
    ordinary missing key, because the text is right there in the file when
    somebody goes looking for it.

    The card is named as a guard on the reading: a pattern that matched nothing
    would make every assertion here pass over an empty list.
    """
    bundle = i18n_core.get_translator(locale)
    written = sorted({key for path in _locale_files(locale) for key in _keys_in(path)})

    dropped = [key for key in written if not _has_message(bundle, key)]

    assert text_keys.CATALOG_CARD in written
    assert dropped == []


@pytest.mark.parametrize("locale", LOCALES)
def test_no_message_is_written_that_nothing_ever_asks_for(locale: str) -> None:
    """Wording nobody can reach is wording nobody maintains.

    A key renamed in ``text_keys`` leaves its old text behind in both
    languages, and every other test here keeps passing: the two files still
    agree with each other, every declared key still has a message, and the
    orphan sits in the middle of the file looking exactly like the message the
    screen is using. The next person to edit the wording has an even chance of
    editing the dead copy.
    """
    referenced = _references_in(locale)
    declared = set(declared_keys())

    orphans = sorted(
        f"{key} in {path.name}"
        for path in _locale_files(locale)
        for key in _keys_in(path)
        if key not in declared and key not in referenced
    )

    assert orphans == []


def test_both_languages_define_the_same_keys() -> None:
    """A key translated into one language only is a screen in two languages."""
    russian, english = (
        {key for path in _locale_files(locale) for key in _keys_in(path)}
        for locale in ("ru", "en")
    )

    assert sorted(russian ^ english) == []


@pytest.mark.parametrize("locale", LOCALES)
def test_no_message_references_one_that_does_not_exist(
    locale: str,
    i18n_core: BaseCore[Any],
) -> None:
    """The composed screens are held together by references, and nothing checks them.

    Four keys embed another message — the product card pulls in ``catalog-sku``
    and ``stock-badge``, the two order cards pull in ``order-status``, and the
    "done" screen pulls in ``order-card-next-steps``. A reference to a key
    nobody wrote does not fail the import, the type checker or the "every key
    has a message" test above: it renders as the literal ``{catalog-sku}`` in
    the middle of the screen and is reported only as an error nobody reads.

    Rendering with no arguments deliberately produces a pile of unknown
    externals, and those are ignored here — the point is that no error is about
    a *message* or a *term*.
    """
    bundle = i18n_core.get_translator(locale)

    dangling = [
        f"{key}: {error}"
        for key in declared_keys()
        for error in _render_errors(bundle, key)
        if not error.startswith(_UNKNOWN_EXTERNAL)
    ]

    assert dangling == []


def test_both_languages_ask_their_screens_for_the_same_arguments(
    i18n_core: BaseCore[Any],
) -> None:
    """Because a getter feeds one set of arguments to both languages.

    Nothing pairs a window's getter with the ``.ftl`` it renders, so a Russian
    message that grew a ``{ $stock }`` its English twin never got is invisible
    until somebody switches language — and then it does not render at all,
    because an unknown external raises rather than printing itself.

    The contract is discovered by rendering rather than by parsing: ask for the
    key, collect the externals Fluent says it does not know, supply them, ask
    again. That follows references into the messages they embed and settles on
    everything the screen actually demands.
    """
    russian, english = (_argument_contracts(i18n_core, locale) for locale in ("ru", "en"))

    differing = {
        key: sorted(russian[key] ^ english[key])
        for key in russian
        if russian[key] != english[key]
    }

    assert differing == {}


def _argument_contracts(
    core: BaseCore[Any],
    locale: str,
) -> dict[str, frozenset[str]]:
    bundle = core.get_translator(locale)

    return {key: _arguments_of(bundle, key) for key in declared_keys()}


def _arguments_of(bundle: FluentBundle, key: str) -> frozenset[str]:
    """Every variable the key needs, found by rendering until it stops complaining.

    Iterative because a selector hides its branches: ``stock-badge`` asks only
    for ``in_stock`` until that variable exists, and only then admits it also
    wants ``stock`` and ``unit``. The loop is bounded by the fact that each pass
    must add a name or stop.
    """
    known: dict[str, str] = {}

    while True:
        missing = {
            error.removeprefix(_UNKNOWN_EXTERNAL)
            for error in _render_errors(bundle, key, known)
            if error.startswith(_UNKNOWN_EXTERNAL)
        } - known.keys()

        if not missing:
            return frozenset(known)

        known.update(dict.fromkeys(missing, "1"))


def _render_errors(
    bundle: FluentBundle, key: str, args: dict[str, str] | None = None
) -> list[str]:
    """Whatever Fluent complained about while drawing that message.

    A message carrying only attributes has no pattern to draw and nothing to
    complain about; ``test_every_declared_key_has_a_message`` is what says none
    of ours is shaped that way.
    """
    pattern = bundle.get_message(key).value

    if pattern is None:
        return []

    _, errors = bundle.format_pattern(pattern=pattern, args=args or {})

    return [str(error) for error in errors]


def _references_in(locale: str) -> set[str]:
    """Every message the translations of that language embed in another."""
    return {
        match.group(1)
        for path in _locale_files(locale)
        for match in MESSAGE_REFERENCE.finditer(path.read_text(encoding="utf-8"))
    }


def _locale_files(locale: str) -> list[Path]:
    return sorted((LOCALES_PATH / locale / "LC_MESSAGES").glob("*.ftl"))


def _keys_in(path: Path) -> Iterator[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        match = MESSAGE_DEFINITION.match(line)

        if match is not None:
            yield match.group(1)


def _has_message(bundle: FluentBundle, key: str) -> bool:
    try:
        message = bundle.get_message(key)
    except LookupError:
        return False

    return message.value is not None
