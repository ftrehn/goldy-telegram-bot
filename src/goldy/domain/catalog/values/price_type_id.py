from dataclasses import dataclass

from goldy.domain.catalog.values.source_id import SourceId


@dataclass(frozen=True, kw_only=True)
class PriceTypeId(SourceId):
    """The price list a person is shown prices from, as 1C references it.

    A reference and not a code: in 1C ``Код`` and ``Ссылка`` are two different
    attributes, and the projection is keyed by the reference. The
    human-readable code and name stay attributes of the projection row — the
    domain has no use for either and would only drift from them.

    Which price type a person is on is decided by the projection, keyed by
    phone number, with a default configured on the bot. It is deliberately not
    a field of ``User``: see ADR-0003.
    """
