from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CatalogConfig:
    """Our own decisions about a catalog we do not own.

    1C has no "main price type" flag to send us: in a standard installation the
    price list a customer buys at follows from an agreement or a sales setting,
    so the consumer would have nowhere to read it from and the field would be
    filled by convention anyway. Since the choice is ours, it lives where our
    choices live rather than in the exchange contract.

    Attributes:
        default_price_type_id: The price list shown to a customer the catalog
            holds no binding for. Kept as the raw identifier because a config
            object reads the environment and nothing more; turning it into a
            ``PriceTypeId`` is the composition root's job, the same way parsed
            administrator numbers reach ``StaticAdminRegistry``.
    """

    default_price_type_id: str = ""
