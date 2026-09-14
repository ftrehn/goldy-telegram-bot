from aiogram.fsm.state import State, StatesGroup


class CartStates(StatesGroup):
    """Screens of the cart dialog.

    ``MAIN`` is the hub every action comes back to, so a person always ends up
    looking at the cart they have just changed.

    ``LINE`` exists because the buttons that change one position do not fit
    beside it. A cart holds up to a hundred products, and drawing ``-``, ``+``,
    "quantity" and "remove" next to every one of them would be four hundred
    buttons on a screen whose own text is the thing worth reading. One button
    per line that opens the line is what keeps the list a list.
    """

    MAIN = State()
    LINE = State()
    QUANTITY = State()
    CLEAR_CONFIRM = State()
