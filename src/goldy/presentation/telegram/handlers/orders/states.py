from aiogram.fsm.state import State, StatesGroup


class OrdersStates(StatesGroup):
    """Screens of a customer's own order history.

    ``LIST`` is the hub and ``CARD`` is one order; the leaves are the only
    things a buyer may still do with a placed order — retype the address it is
    going to, take the order back, and buy the same thing again.

    All of them return to ``CARD`` rather than to ``LIST``, so the screen that
    comes back is the one showing what just changed.

    The repeat has two screens rather than one because it has two kinds of
    outcome. ``REPEAT_CONFIRM`` is where the cart is told what is about to
    happen to it, and ``REPEAT_RESULT`` is reached only when something could
    not be carried over — a complete repeat says so in a toast and goes
    straight back to the card, since there is nothing there to read.
    """

    LIST = State()
    CARD = State()
    EDIT_ADDRESS = State()
    CANCEL_CONFIRM = State()
    REPEAT_CONFIRM = State()
    REPEAT_RESULT = State()
