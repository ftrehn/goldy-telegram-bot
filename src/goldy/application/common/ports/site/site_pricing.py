from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.values.money import Money
from goldy.domain.common.values.quantity import Quantity


@dataclass(frozen=True, slots=True)
class SitePriceRequest:
    """One position to price, with the quantity it will be bought in."""

    product_id: ProductId
    quantity: Quantity


@dataclass(frozen=True, slots=True)
class SitePrice:
    """The site's price for one position, for one linked customer.

    ``unit_price`` is ``None`` when the site will not sell it to this customer
    — hidden, archived, no price — and ``reason`` says which, in the site's own
    word. A missing price is a refusal to price, never a zero.
    """

    product_id: ProductId
    unit_price: Money | None
    reason: str | None


class SitePricing(Protocol):
    """Prices positions for a linked customer the way the site's cart would.

    The site is the one that knows the company's discount, the contract prices
    and min(BASE, OPT); the bot does not repeat any of it. **Nothing behind
    this port may be cached**: the answer is about to become an order line.
    """

    @abstractmethod
    async def prices_for(
        self,
        subject: str,
        items: Sequence[SitePriceRequest],
    ) -> Sequence[SitePrice]:
        """The customer's price for every requested position, in one call.

        Raises:
            SiteCustomerNotLinkedError: the site no longer knows the subject.
            SiteUnavailableError: the site did not answer.
        """
        raise NotImplementedError
