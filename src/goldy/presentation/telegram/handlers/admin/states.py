from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Screens of the admin dialog.

    ``USERS`` is the list, ``CARD`` is one person, and the two leaves are the
    actions that need something typed or picked before they can run.
    """

    USERS = State()
    CARD = State()
    BLOCK_REASON = State()
    ROLE = State()
