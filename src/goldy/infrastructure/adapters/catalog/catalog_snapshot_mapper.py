from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.application.common.ports.catalog import CatalogSnapshot


class CatalogSnapshotMapper(Protocol):
    """Turns a decoded document — whatever JSON spelled — into a snapshot.

    An infrastructure port, like the row mappers: its input is the raw shape
    of an exchange file, which the application has no business knowing. The
    source adapter reads bytes and decodes JSON; this port decides whether what
    came out is a snapshot, and says exactly where it is not.

    A port so that the seeder's file today and the HTTP receiver 1C posts to
    tomorrow can share one reading of the contract, and so that the reading
    can be replaced — a different 1C export, a different mapper — without the
    source that feeds it changing.
    """

    @abstractmethod
    def to_snapshot(self, document: object) -> CatalogSnapshot:
        """The batch the document describes.

        Raises:
            CatalogSourceReadError: the document is not shaped like a snapshot,
                naming the field that was wrong.
        """
        raise NotImplementedError
