from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, cast, override

from dature import EnvSource

from goldy.setup.bootstrap.sources.source_factory import SourceFactory

if TYPE_CHECKING:
    from dature.sources.protocol import SourceProtocol
    from dature.type_aliases import FieldMapping, JSONValue


@dataclass(kw_only=True, repr=False)
class DictSource(EnvSource):
    """A dature source that serves values straight from a dict.

    Reuses ``EnvSource``'s field mapping and type conversion, but overrides
    :meth:`_load` to return an in-memory mapping instead of ``os.environ`` — no
    files, no ``.env`` parsing, no environment access, so tests cannot leak into
    each other through the process environment.
    """

    data: dict[str, str] = field(default_factory=dict)

    @override
    def _load(self) -> JSONValue:
        return cast("JSONValue", self.data)


class StubSourceFactory(SourceFactory):
    """In-memory :class:`SourceFactory` for tests.

    Implements the production protocol and serves fixed values from a plain
    dict, so loading is deterministic. :meth:`mirroring` reuses a real
    factory's ``field_mapping``, which is what makes a test keyed by real
    environment variable names also prove that the mapping itself is right — a
    typo in the production mapping breaks the test instead of hiding behind it.
    """

    def __init__(
        self,
        values: dict[str, str],
        field_mapping: FieldMapping | None = None,
    ) -> None:
        self._values = values
        self._field_mapping = field_mapping

    @override
    def create(self) -> SourceProtocol:
        return DictSource(data=self._values, field_mapping=self._field_mapping)

    @classmethod
    def mirroring(cls, factory: SourceFactory, values: dict[str, str]) -> Self:
        """Builds a stub reusing ``factory``'s environment-name mapping."""
        field_mapping = getattr(factory.create(), "field_mapping", None)
        return cls(values=values, field_mapping=field_mapping)
