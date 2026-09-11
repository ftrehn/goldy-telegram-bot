from aiogram.fsm.state import State, StatesGroup


class CatalogStates(StatesGroup):
    """Screens of the storefront dialog.

    ``CATEGORIES`` is the hub: the tree is walked one level at a time, and
    every other screen leads back to it. ``PRODUCTS`` and ``RESULTS`` are the
    two paged listings — a category subtree and a set of search results — and
    they are two states rather than one because they are paged separately and
    reached from different places.

    ``CARD`` is opened from either listing and remembers which one, so "back"
    returns to the list the person was reading instead of dropping them at the
    top of the catalog. ``DESCRIPTION`` exists because the card is a photo with
    a caption, and a caption is limited to a quarter of what a message holds.

    There is no state for "nothing found": whether a search matched is known
    only after the query the ``RESULTS`` getter runs, and a getter must not
    switch states — so the empty outcome is the same window rendered without a
    list.
    """

    CATEGORIES = State()
    PRODUCTS = State()
    CARD = State()
    DESCRIPTION = State()
    SEARCH = State()
    RESULTS = State()
