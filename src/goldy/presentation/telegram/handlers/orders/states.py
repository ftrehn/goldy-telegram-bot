from aiogram.fsm.state import State, StatesGroup


class OrdersStates(StatesGroup):
    """Screens of a customer's own order history.

    ``LIST`` is the hub and ``CARD`` is one order; the two leaves are the only
    things a buyer may still do to a placed order — retype the address it is
    going to, and take the order back.

    Both leaves return to ``CARD`` rather than to ``LIST``, so the screen that
    comes back is the one showing what just changed.
    """

    LIST = State()
    CARD = State()
    EDIT_ADDRESS = State()
    CANCEL_CONFIRM = State()
