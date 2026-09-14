from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from goldy.application.common.ports.catalog.catalog_snapshot import (
        CatalogScope,
        CategoryRow,
        PriceRow,
        PriceTypeBindingRow,
        PriceTypeRow,
        ProductRow,
        StockRow,
    )
    from goldy.domain.catalog.values.price_type_id import PriceTypeId


class CatalogProjectionDao(Protocol):
    """The only way anything is ever written into the catalog projection.

    A DAO and not a gateway, and the name is a promise about the shape of the
    methods. A gateway in this project is thin — it hands whole aggregates
    in and out and lets the unit of work do the writing — while this port
    takes batches of rows and upserts them, sweeps by a stamp and counts what
    it touched. That is data access written for throughput, and calling it a
    gateway would invite somebody to expect an aggregate behind it. There is
    none: the projection is Core-only and builds no domain values on its way
    in.

    Upserts take a batch in and stamp ``batch_id`` on every row they touch;
    :meth:`finalize` removes what that batch did not mention. The two are
    separate because 1C sends its data in parts, and a single call meaning
    "this is the whole catalog now" would let the second part erase the first.

    Upserts are unconditional: a row that arrives replaces the row stored,
    and ``source_changed_at`` is kept as a fact about the row rather than
    used as a guard. The exchange with 1C is synchronous and ordered
    (ADR-0004), and its one sender posts the current state of 1C on every
    run, so there is no older delivery that could arrive after a newer one.
    What does arrive is a price 1C rolled back to an earlier date, and a
    write conditional on the date would refuse exactly that row — leave it
    unstamped, and the sweep would take it for absent.

    Two things are decided where the rows are written rather than by a handler,
    because both are properties of the projection. ``path`` and ``depth`` on a
    category are computed from the batch as a whole, which the contract
    guarantees is the complete category snapshot. ``is_supported`` on a price
    type is whether its currency is a member of ``Currency``; an unsupported
    price list is stored rather than dropped, so a customer bound to it is
    refused plainly instead of shown somebody else's prices.

    Every method returns how many rows it affected, for the import log.
    """

    @abstractmethod
    async def upsert_categories(
        self,
        categories: Sequence[CategoryRow],
        batch_id: str,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def upsert_products(self, products: Sequence[ProductRow], batch_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def upsert_price_types(
        self,
        price_types: Sequence[PriceTypeRow],
        batch_id: str,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def upsert_prices(self, prices: Sequence[PriceRow], batch_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def upsert_stock(self, stock: Sequence[StockRow], batch_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def upsert_price_type_bindings(
        self,
        bindings: Sequence[PriceTypeBindingRow],
        batch_id: str,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def finalize(self, scope: CatalogScope, batch_id: str) -> int:
        """Removes what this batch did not mention, within its scope.

        What "removes" means depends on the scope, and confusing the two would
        be expensive. Products and categories are **deactivated** and kept
        forever, because placed orders point at them and a card should still
        open in a customer's history. Prices and stock are **deleted**, because
        a price withdrawn in 1C has to disappear: a row that survives forever is
        a price the shop does not offer, which is money lost directly.

        The scope narrows the deletion to one price list or one warehouse, so
        exporting a single price list cannot wipe the others. The one sweep
        that reaches across tables is the one over price types: a price list
        the source stopped sending takes its prices and bindings with it,
        because no later batch will ever be about that list and its own sweep
        would never come.
        """
        raise NotImplementedError

    @abstractmethod
    async def has_price_type(self, price_type_id: PriceTypeId) -> bool:
        """Whether the projection holds this price list after the sweep.

        Asked once, when an import is finalised, about the price type
        configured as the default. A missing default is a broken snapshot, and
        the refusal belongs to whoever ran the import rather than to the first
        customer who opens the catalog.
        """
        raise NotImplementedError
