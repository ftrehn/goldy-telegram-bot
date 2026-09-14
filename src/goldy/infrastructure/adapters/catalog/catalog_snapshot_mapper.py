from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.application.common.ports.catalog import CatalogScope, CatalogSnapshot


class CatalogSnapshotMapper(Protocol):
    """Turns a decoded document — whatever JSON spelled — into a snapshot.

    An infrastructure port, like the row mappers: its input is the raw shape
    of an exchange file, which the application has no business knowing. The
    source adapter reads bytes and decodes JSON; this port decides whether what
    came out is a snapshot, and says exactly where it is not.

    A port so that the seeder's file and the HTTP receiver 1C posts to share
    one reading of the contract, and so that the reading can be replaced — a
    different 1C export, a different mapper — without the source that feeds it
    changing.

    Two methods because 1C talks to the receiver in two kinds of body. A batch
    is a whole snapshot; a finalisation carries nothing but the scope it
    closes, and the scope alone has to be read by the same rules a snapshot's
    is, or a typo that one reading refuses would slip past the other and sweep
    the wrong part of the catalog.
    """

    @abstractmethod
    def to_snapshot(self, document: object) -> CatalogSnapshot:
        """The batch the document describes.

        Raises:
            CatalogSourceReadError: the document is not shaped like a snapshot,
                naming the field that was wrong.
        """
        raise NotImplementedError

    @abstractmethod
    def to_scope(self, document: object) -> CatalogScope:
        """The scope the document describes.

        *document* is the scope object itself — what sits under the ``scope``
        key of a snapshot or of a finalisation body — not the body around it.
        Finding that key is the caller's job, because only the caller knows
        what the body was; naming a wrong field from that key on is this
        method's, so the refusal reads as ``scope.kind`` wherever the scope
        came from.

        Raises:
            CatalogSourceReadError: the document is not shaped like a scope,
                naming the field that was wrong.
        """
        raise NotImplementedError
