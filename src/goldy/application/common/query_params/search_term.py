from dataclasses import dataclass
from typing import Final

from goldy.application.error import SearchTermError

MIN_SEARCH_TERM_LENGTH: Final[int] = 2
MAX_SEARCH_TERM_LENGTH: Final[int] = 128


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchTerm:
    """What the customer typed, carried raw and checked for length only.

    Raw on purpose. Normalisation — folding ``AB-123``, ``ab 123`` and
    ``ab123`` together, and the two spellings of the Russian ``yo`` — has to
    agree exactly with the generated columns Postgres computes, so it lives
    next to them inside the catalog gateway. Doing it here would mean the
    application layer importing ``infrastructure.persistence.models``, which
    the layers contract refuses on the first run.

    Length is the one thing this layer can judge without knowing any of that,
    and it judges it once rather than in the handler, the way ``Pagination``
    already does with its bounds.
    """

    value: str

    def __post_init__(self) -> None:
        length = len(self.value.strip())

        if length < MIN_SEARCH_TERM_LENGTH:
            msg = (
                f"Search term must be at least {MIN_SEARCH_TERM_LENGTH} "
                f"characters, got {length}."
            )
            raise SearchTermError(msg)

        if length > MAX_SEARCH_TERM_LENGTH:
            msg = (
                f"Search term cannot be longer than {MAX_SEARCH_TERM_LENGTH} "
                f"characters, got {length}."
            )
            raise SearchTermError(msg)
