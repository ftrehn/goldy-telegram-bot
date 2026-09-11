"""Catalog values — and deliberately nothing else.

The catalog lives in 1C and the bot only reads it: it does not create, change
or delete a product, and there is no synchronisation back. So the product has
not one rule of *ours* to enforce, and an aggregate ``Product`` would be a bag
of fields with no methods, dragging behind it a command gateway nobody writes
through and a factory minting identifiers we do not own.

What the domain does need are the values an order keeps a snapshot of, because
an ``OrderLine`` with an empty name or a negative price is our bug and has to
be refused here. Hence this package holds value objects and their errors only.

**Do not add an aggregate here.** If a rule about a product has appeared, it is
a rule about an order or about a price type; the product itself has none. The
read model of the catalog belongs to infrastructure, and searching it by name
or SKU is a query-side concern the domain never sees.
"""
