"""Where a link lands in the storefront, including when it leads nowhere.

The interesting cases here are all failures, and each of them is a link that
was correct on the day it was printed onto a web page. Products are withdrawn
by an import sweep and sections disappear with them, so "the link is stale" is
the ordinary state of a link, not an edge case — and the requirement is that a
stale one never looks like a broken bot.
"""

from typing import cast, final, override

import pytest

from goldy.application.common.mediator.markers import BaseRequest
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.catalog import CategoryListView, ProductView
from goldy.application.error import (
    ProductNotFoundError,
    UnsupportedPriceTypeError,
)
from goldy.application.queries.catalog.get_product.query import GetProductQuery
from goldy.application.queries.catalog.list_categories.query import ListCategoriesQuery
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.deeplinks import DeepLinkKind, DeepLinkTarget
from goldy.presentation.telegram.handlers.catalog.deeplinks import (
    CATEGORY_ID_KEY,
    CATEGORY_NAME_KEY,
    resolve_deeplink,
)
from goldy.presentation.telegram.handlers.catalog.getters import PRODUCT_ID_KEY
from goldy.presentation.telegram.handlers.catalog.states import CatalogStates
from tests.unit.factories.catalog_factories import (
    make_category_view,
    make_product_view,
)


@final
class StubSender(Sender):
    """Answers the two reads a deep link makes, and refuses everything else.

    A stub rather than a stubbed gateway because what is under test is a
    decision taken above the mediator: which screen opens. Going through real
    handlers would mean a price type provider, an identity provider and a
    catalog gateway, none of which change the answer.
    """

    def __init__(
        self,
        *,
        product: ProductView | None = None,
        category_list: CategoryListView | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.product = product
        self.category_list = category_list
        self.failure = failure
        self.requests: list[BaseRequest[object]] = []

    @override
    async def send[TResponse](self, request: BaseRequest[TResponse]) -> TResponse:
        self.requests.append(cast("BaseRequest[object]", request))

        if self.failure is not None:
            raise self.failure

        if isinstance(request, GetProductQuery) and self.product is not None:
            return cast("TResponse", self.product)

        if isinstance(request, ListCategoriesQuery) and self.category_list is not None:
            return cast("TResponse", self.category_list)

        msg = f"Nothing here answers {type(request).__name__}."
        raise AssertionError(msg)


async def test_a_live_product_opens_its_own_card() -> None:
    """The whole point of the feature, stated as one assertion."""
    product = make_product_view()
    sender = StubSender(product=product)

    entry = await resolve_deeplink(sender, _product_link(product.id))

    assert entry.state == CatalogStates.CARD
    assert entry.data == {PRODUCT_ID_KEY: product.id}
    assert entry.notice is None


async def test_a_product_the_catalog_no_longer_has_sends_the_visitor_to_the_top() -> None:
    """A refusal here would be the worst available answer.

    The visitor is a stranger who tapped a button on the shop's own website. A
    bot that answers them with an error has told them the shop is broken, when
    the truth is that one product moved.
    """
    sender = StubSender(failure=ProductNotFoundError("gone"))

    entry = await resolve_deeplink(sender, _product_link("no-such-product"))

    assert entry.state == CatalogStates.CATEGORIES
    assert entry.notice == text_keys.DEEPLINK_PRODUCT_GONE
    assert entry.data == {}


async def test_a_deactivated_product_is_gone_even_though_it_still_reads() -> None:
    """The case a card getter cannot catch, and the reason this check exists.

    An import sweep deactivates rather than deletes, because placed orders
    point at the row — so the product reads back perfectly and only
    ``is_active`` says the shop has stopped selling it. Every other way into a
    card comes through a listing that has already filtered on that flag; a link
    has no listing in front of it.
    """
    sender = StubSender(product=make_product_view(is_active=False))

    entry = await resolve_deeplink(sender, _product_link("withdrawn"))

    assert entry.state == CatalogStates.CATEGORIES
    assert entry.notice == text_keys.DEEPLINK_PRODUCT_GONE


async def test_a_fault_of_ours_is_not_dressed_up_as_a_dead_link() -> None:
    """Only "this product is gone" is swallowed, and deliberately only that.

    A price type in a currency the service does not know is our defect and has
    its own wording in the error table. Catching it here would tell a customer
    the product no longer exists while it sits priced in the catalog, and would
    keep the real fault out of the log.
    """
    sender = StubSender(failure=UnsupportedPriceTypeError("unknown currency"))

    with pytest.raises(UnsupportedPriceTypeError):
        await resolve_deeplink(sender, _product_link("priced-oddly"))


async def test_a_live_category_opens_standing_inside_it() -> None:
    """With the crumb that makes "one level up" work from a cold start.

    The tree is normally walked one tap at a time and the breadcrumb is built
    from those taps. A link arrives with no taps behind it, so the first crumb
    is handed over as start data instead — name included, because the heading
    falls back to it.
    """
    category = make_category_view(index=3)
    sender = StubSender(category_list=CategoryListView(parent=category, categories=()))

    entry = await resolve_deeplink(sender, _category_link(category.id))

    assert entry.state == CatalogStates.CATEGORIES
    assert entry.data == {
        CATEGORY_ID_KEY: category.id,
        CATEGORY_NAME_KEY: category.name,
    }
    assert entry.notice is None


async def test_a_swept_category_says_so_instead_of_looking_like_the_top() -> None:
    """``parent=None`` is the only sign, and without this check it is invisible.

    The read side refuses an inactive category and answers with the level
    anyway, so a swept group renders as an ordinary screen with a missing
    heading — indistinguishable, to the customer, from having been dropped at
    the top of the catalog for no reason.
    """
    sender = StubSender(category_list=CategoryListView(parent=None, categories=()))

    entry = await resolve_deeplink(sender, _category_link("swept"))

    assert entry.state == CatalogStates.CATEGORIES
    assert entry.notice == text_keys.DEEPLINK_CATEGORY_GONE
    assert entry.data == {}


async def test_a_payload_that_did_not_parse_reads_the_catalog_nothing() -> None:
    """Rubbish costs no query at all, which is also the point.

    ``None`` is what a truncated, forged or simply unknown payload decodes to.
    There is nothing to look up — it names no product and no section — so the
    answer is the catalog and a sentence, and the database is never touched.
    """
    sender = StubSender()

    entry = await resolve_deeplink(sender, None)

    assert entry.state == CatalogStates.CATEGORIES
    assert entry.notice == text_keys.DEEPLINK_PRODUCT_GONE
    assert sender.requests == []


def _product_link(product_id: str) -> DeepLinkTarget:
    return DeepLinkTarget(kind=DeepLinkKind.PRODUCT, id=product_id)


def _category_link(category_id: str) -> DeepLinkTarget:
    return DeepLinkTarget(kind=DeepLinkKind.CATEGORY, id=category_id)
