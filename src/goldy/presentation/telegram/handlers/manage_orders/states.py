from aiogram.fsm.state import State, StatesGroup


class ManageOrdersStates(StatesGroup):
    """Screens of the staff order queue.

    A states group of its own rather than four more members on ``AdminStates``.
    The admin dialog is about people — list, block, role — and this is about
    orders; stitched together, the shared "back" button would have to remember
    which hub it was reached from, which is state existing only to serve the
    stitching.

    ``CANCEL_REASON`` hangs off ``STATUS`` because it is not a status of its
    own: it is the one move the aggregate refuses without a sentence, and the
    manager is asked for that sentence on the way rather than afterwards.
    """

    QUEUE = State()
    CARD = State()
    FILTER = State()
    STATUS = State()
    CANCEL_REASON = State()
