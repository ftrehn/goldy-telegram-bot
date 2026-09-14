"""Whether the screens that exist are screens anybody can reach.

Every dialog in this project is correct on its own and invisible until it is
attached, and nothing in the type checker or the linter notices the difference.
A dialog left out of ``DIALOGS`` is a command that answers "unknown command"; a
button pointing at a state group nobody registered is a tap that raises; a
feature router attached below the dialogs is ``/cart`` swallowed as a search
term by whichever catalog window happened to be open. All four are wiring, all
four look exactly like working code, and all four are found here by building
the real dispatcher rather than by reading the tuples.
"""

from collections.abc import Iterable, Iterator
from typing import Any, final, override

import pytest
from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup
from aiogram_i18n.cores import BaseCore

from goldy.domain.users.values.locale import DEFAULT_LOCALE
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import ENGLISH_LOCALE, NO, YES
from goldy.presentation.telegram.handlers.routers import (
    DIALOGS,
    FEATURE_ROUTERS,
    LAST_ROUTERS,
    setup_all_handlers,
)
from goldy.setup.bootstrap.setups.telegram_setup import PUBLISHED_COMMANDS
from tests.unit.presentation.telegram.widgets import texts_of, walk

LOCALES = (DEFAULT_LOCALE, ENGLISH_LOCALE)

BRANCHES = (YES, NO)
"""Both sides of every Fluent selector any screen draws.

A placeable inside the ``[yes]`` branch is never evaluated while the flag says
something else, so filling every argument with one word would let a screen that
only breaks for a priced product pass. Rendering twice covers both sides.
"""

STAFF_COMMAND = "manage_orders"


def test_every_published_command_is_actually_handled() -> None:
    """A menu entry with no handler is a button that answers "unknown command".

    The menu is written out by hand in ``telegram_setup`` — deliberately, so
    that leaving the staff command out of it is a decision rather than an
    accident — and the price of writing it by hand is that nothing ties it to
    the routers. This is that tie.
    """
    handled = _handled_commands(FEATURE_ROUTERS)

    assert sorted(set(PUBLISHED_COMMANDS) - handled) == []


def test_the_staff_command_is_reachable_and_unpublished() -> None:
    """Both halves matter, and they pull in opposite directions.

    ``help-staff`` exists so that a customer is never told staff commands are
    there, and a published menu would walk around it. But an unpublished
    command that is also unregistered is simply missing, and its symptom —
    "unknown command" — is the very answer the staff filter is supposed to give
    a customer, so the mistake would look like the feature working.
    """
    assert STAFF_COMMAND in _handled_commands(FEATURE_ROUTERS)
    assert STAFF_COMMAND not in PUBLISHED_COMMANDS


@final
class AttachmentOrder(Dispatcher):
    """A dispatcher that writes down what it was given instead of taking it.

    A real one cannot be used twice: routers are module-level singletons and
    aiogram refuses to attach one that already has a parent. The integration
    suite assembles the genuine article — once, for the whole session — and
    this unit test must not spend that one attachment, or running both suites
    in a single process would fail on whichever went second.

    What is under test here is the *order* ``setup_all_handlers`` hands them
    over in, and that is visible without attaching anything.
    """

    def __init__(self) -> None:
        super().__init__()
        self.attached: list[Router] = []

    @override
    def include_router(self, router: Router) -> Router:
        self.attached.append(router)

        return router


def test_feature_routers_are_tried_before_dialogs_and_the_fallback() -> None:
    """The ordering the catalog's typed-text search rests on.

    Three catalog windows treat any typed text as a search term. Attached above
    the feature routers, they would take ``/cart`` as a search for the word
    "/cart" — and a command is wanted most precisely when somebody is in the
    middle of something else. The fallback matches everything, so anything
    below it never runs at all.
    """
    order = AttachmentOrder()
    setup_all_handlers(order)

    positions = {router.name: index for index, router in enumerate(order.attached)}

    last_feature = max(positions[router.name] for router in FEATURE_ROUTERS)
    first_dialog = min(positions[dialog.name] for dialog in DIALOGS)
    first_last = min(positions[router.name] for router in LAST_ROUTERS)

    assert last_feature < first_dialog < first_last


def test_every_router_and_dialog_is_handed_over_exactly_once() -> None:
    """Twice is not harmless: aiogram raises on the second attachment.

    Which means a duplicate entry in one of the three tuples is not a screen
    that answers twice, it is a bot that will not start — and the place it
    fails is the entry point, far from the tuple that caused it.
    """
    order = AttachmentOrder()
    setup_all_handlers(order)

    names = [router.name for router in order.attached]

    assert sorted(names) == sorted(set(names))


def test_every_dialog_owns_a_state_group_of_its_own() -> None:
    """Two dialogs sharing a group would route half of each other's taps.

    aiogram-dialog picks a dialog by the state group the person is standing in
    rather than by attachment order, so a shared group is not resolved by
    putting one of them first — it is simply ambiguous.
    """
    groups = {dialog.states_group() for dialog in DIALOGS}

    assert len(groups) == len(tuple(DIALOGS))


def test_every_state_group_a_button_starts_is_registered() -> None:
    """A ``Start`` naming a dialog nobody attached raises when it is tapped.

    The storefront is stitched together by these: the cart opens checkout, the
    card opens the cart, the "done" screen opens the catalog. Each one names a
    state group rather than a dialog object, so a reference to an unattached
    dialog type-checks perfectly well.
    """
    registered = {dialog.states_group() for dialog in DIALOGS}

    unreachable = sorted(
        str(state)
        for dialog in DIALOGS
        for state in _started_states(dialog)
        if _group_of(state) not in registered
    )

    assert unreachable == []


def test_the_walk_reaches_a_screen_of_every_dialog() -> None:
    """Guards the walk below: one that finds nothing passes in silence.

    Named keys rather than a count, because a count drifts with every screen
    somebody adds, and a test nobody trusts is a test nobody fixes.
    """
    keys = {widget.text for widget in texts_of(DIALOGS)}

    assert {
        text_keys.ADMIN_USER_CARD,
        text_keys.CART_LINE,
        text_keys.CATALOG_CARD,
        text_keys.CHECKOUT_DONE,
        text_keys.MANAGE_ORDERS_CARD,
        text_keys.ORDER_CARD,
        text_keys.PROFILE_RENAME_PROMPT,
    } <= keys


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("branch", BRANCHES)
def test_every_screen_of_every_dialog_renders_in_both_languages(
    i18n_core: BaseCore[Any],
    locale: str,
    branch: str,
) -> None:
    """Rendering without raising is the whole assertion.

    Four keys embed another message, and an embedded Fluent message reads the
    arguments of the message that referenced it. Get that wrong and the core
    raises ``FluentMessageError`` rather than leaving ``{ $sku }`` in the text,
    so the screen does not appear at all — and the first reader is a customer.
    The values here are meaningless; the argument *names* are the contract.
    """
    for widget in texts_of(DIALOGS):
        arguments = dict.fromkeys(widget.mapping, branch)

        i18n_core.get(widget.text, locale, **arguments)


def _handled_commands(routers: Iterable[Router]) -> set[str]:
    """Every command word the given routers claim."""
    return {
        command
        for router in routers
        for handler in router.message.handlers
        for filter_object in handler.filters or ()
        if isinstance(filter_object.callback, Command)
        for command in filter_object.callback.commands
        if isinstance(command, str)
    }


def _started_states(node: object) -> Iterator[Any]:
    """The state every ``Start``-like widget in a dialog points at.

    Found by attribute rather than by class, because ``Start`` is the base of
    the widgets that subclass it and a check against one name would miss them.
    Only widgets that carry a ``state`` and are not windows qualify — a window
    owns the state it *is*, which is registered by construction.
    """
    for widget in walk(node):
        state = getattr(widget, "state", None)

        if _group_of(state) is not None and hasattr(widget, "on_click"):
            yield state


def _group_of(state: Any) -> type[StatesGroup] | None:
    """The state group a widget points at, if it points at one at all."""
    group = getattr(state, "group", None)

    return group if isinstance(group, type) else None
