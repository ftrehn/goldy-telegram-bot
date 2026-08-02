from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    """Screens of the profile dialog.

    ``MAIN`` is the hub every other screen returns to, so a person always ends
    up looking at the thing they just changed.
    """

    MAIN = State()
    RENAME = State()
    LOCALE = State()
    NOTIFICATIONS = State()
    ACCOUNTS = State()
