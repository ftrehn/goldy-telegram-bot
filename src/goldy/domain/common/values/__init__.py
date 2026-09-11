"""Value objects that no single aggregate owns.

``Money``, ``Currency`` and ``Quantity`` are used by the catalog, the cart and
the order alike. Putting them under ``catalog/values`` would make the cart
depend on the catalog just to say "how many", so they live one level up,
beside ``EventId`` — the shared value the domain already had.

The base classes (``Entity``, ``Aggregate``, ``Event``, ``ValueObject``) stay
in ``domain/common`` itself; this subpackage holds concrete values only, so the
two are not read as one pile.
"""
