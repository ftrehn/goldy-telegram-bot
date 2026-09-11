from aiogram.fsm.state import State, StatesGroup


class CheckoutStates(StatesGroup):
    """Screens of the checkout dialog, in the order they are walked.

    A dialog of its own rather than four more screens of the cart, and started
    with an ordinary ``Start``: the cart stays underneath, so "changed my mind"
    is a ``Cancel`` that lands back on the cart with everything still in it.

    ``PLACING`` holds no buttons and is switched to before the command is
    awaited, which is the first of the three defences against a double tap.
    ``ALREADY_PLACED`` is where the second tap ends up when it gets past the
    first — the one that arrived while the first command was still inside its
    transaction, and met a cart that checkout had already emptied.

    ``DONE`` is reached on a stack of its own: the cart a ``Cancel`` would
    return to does not exist any more, so there is nothing left to go back to.
    """

    ADDRESS = State()
    RECIPIENT = State()
    PHONE = State()
    COMMENT = State()
    CONFIRM = State()
    PLACING = State()
    ALREADY_PLACED = State()
    DONE = State()
