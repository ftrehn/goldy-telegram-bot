"""What the worker makes of the site's catalog, and when it refuses to sweep.

The site speaks its own JSON; these tests pin the reading of it into our rows
— the substitutions the contract leaves to us (an article that is missing, a
stock status nobody counts) and the pass-level decisions: one batch id, the
scopes declared up front, pages imported one by one, and a pass that looks
like a broken site refused rather than finalised. And, as for every adapter,
that the only errors leaving it are the port's.
"""

from decimal import Decimal

import httpx
import pytest

from goldy.application.common.ports.catalog import (
    CatalogPull,
    CatalogScope,
    CatalogScopeKind,
    CatalogSnapshot,
)
from goldy.application.error import CatalogSourceError
from goldy.infrastructure.adapters.catalog.site_catalog_source import (
    SiteCatalogSource,
)
from goldy.infrastructure.errors import (
    CatalogSourceReadError,
    CatalogSourceUnavailableError,
    InfrastructureError,
)
from tests.unit.factories.site_api_factories import (
    SITE_PRICE_TYPE_ID,
    make_site_item,
    make_site_item_id,
    make_site_section,
)
from tests.unit.stubs.site_api import FakeSiteCatalog


async def batches_of(pull: CatalogPull) -> list[CatalogSnapshot]:
    return [snapshot async for snapshot in pull.batches]


async def test_a_pass_declares_every_scope_it_covers_and_never_the_bindings(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """Bindings are not the site's to send; sweeping them would erase the fixture's."""
    fake_site.item_pages = [[make_site_item(1)]]

    pull = await site_catalog_source.pull()

    assert pull.scopes == (
        CatalogScope(kind=CatalogScopeKind.CATEGORIES),
        CatalogScope(kind=CatalogScopeKind.PRODUCTS),
        CatalogScope(kind=CatalogScopeKind.PRICE_TYPES),
        CatalogScope(kind=CatalogScopeKind.PRICES, price_type_id=SITE_PRICE_TYPE_ID),
        CatalogScope(kind=CatalogScopeKind.STOCK, warehouse_id="*"),
    )


async def test_every_batch_of_a_pass_carries_its_one_batch_id(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    fake_site.item_pages = [[make_site_item(1), make_site_item(2)], [make_site_item(3)]]

    pull = await site_catalog_source.pull()
    batches = await batches_of(pull)

    assert {snapshot.batch_id for snapshot in batches} == {pull.batch_id}
    assert len(pull.batch_id) <= 64


async def test_two_passes_get_different_batch_ids(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    fake_site.item_pages = [[make_site_item(1)]]

    first = await site_catalog_source.pull()
    second = await site_catalog_source.pull()

    assert first.batch_id != second.batch_id


async def test_the_tree_and_the_price_lists_come_first_and_in_one_piece(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """Category placement is computed from the whole tree, so it cannot be chunked."""
    fake_site.sections = [
        make_site_section("goldy_sec_1", name="Плинтусы"),
        make_site_section("goldy_sec_2", parent_id="goldy_sec_1", name="Потолочные"),
    ]
    fake_site.item_pages = [[make_site_item(1)]]

    batches = await batches_of(await site_catalog_source.pull())

    categories, price_types = batches[0], batches[1]
    assert [(row.id, row.parent_id) for row in categories.categories] == [
        ("goldy_sec_1", None),
        ("goldy_sec_2", "goldy_sec_1"),
    ]
    assert [(row.id, row.currency) for row in price_types.price_types] == [
        (SITE_PRICE_TYPE_ID, "RUB"),
    ]


async def test_each_page_becomes_its_own_batches_split_by_kind(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """A page is one import per kind — the page size bounds every INSERT."""
    fake_site.item_pages = [[make_site_item(1), make_site_item(2)], [make_site_item(3)]]

    batches = await batches_of(await site_catalog_source.pull())

    kinds = [snapshot.scope.kind for snapshot in batches[2:]]
    assert (
        kinds
        == [
            CatalogScopeKind.PRODUCTS,
            CatalogScopeKind.PRICES,
            CatalogScopeKind.STOCK,
        ]
        * 2
    )
    assert [len(snapshot.products) for snapshot in batches[2::3]] == [2, 1]


async def test_an_item_becomes_a_product_row_in_our_words(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    fake_site.item_pages = [
        [
            make_site_item(
                1,
                unit={"code": "006", "name": "м"},
                ratio="2.5",
                images=["https://tkgoldy.ru/a.jpg", "https://tkgoldy.ru/b.jpg"],
            ),
        ],
    ]

    batches = await batches_of(await site_catalog_source.pull())

    product = batches[2].products[0]
    assert product.id == make_site_item_id(1)
    assert product.sku == "DD501"
    assert product.name == "Потолочный плинтус DD501 DECOR-DIZAYN"
    assert product.category_id == "goldy_sec_12"
    assert (product.unit_id, product.unit_name) == ("006", "м")
    assert product.unit_ratio == Decimal("2.5")
    assert product.description == "Плинтус из полистирола"
    assert product.image_url == "https://tkgoldy.ru/a.jpg"
    assert product.source_changed_at is None


@pytest.mark.parametrize("sku", (None, "", "   ", "X" * 65))
async def test_an_item_without_a_usable_article_is_known_by_its_site_number(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
    sku: str | None,
) -> None:
    """An order line keeps a ``Sku``; the number is what a manager can look up."""
    fake_site.item_pages = [[make_site_item(1, sku=sku)]]

    batches = await batches_of(await site_catalog_source.pull())

    assert batches[2].products[0].sku == "6001"


async def test_the_price_travels_as_text_and_a_missing_one_is_no_row(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """No price means "shown, not sold" on the site; a zero here would read as free."""
    fake_site.item_pages = [[make_site_item(1), make_site_item(2, price=None)]]

    batches = await batches_of(await site_catalog_source.pull())

    prices = next(s for s in batches if s.scope.kind is CatalogScopeKind.PRICES).prices
    assert [(row.product_id, row.amount, row.currency) for row in prices] == [
        (make_site_item_id(1), Decimal("412.00"), "RUB"),
    ]


async def test_a_price_under_a_list_the_pass_did_not_announce_is_dropped(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """It would be stored against a price list nobody sweeps."""
    stray = {"price_type_id": "OPT", "amount": "300.00", "currency": "RUB"}
    fake_site.item_pages = [[make_site_item(1, price=stray)]]

    batches = await batches_of(await site_catalog_source.pull())

    assert not any(snapshot.prices for snapshot in batches)
    assert len(batches[2].products) == 1


async def test_counted_stock_is_a_row_and_untracked_stock_is_none(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """No stock row reads as "made to order", which is exactly what untracked means."""
    fake_site.item_pages = [
        [
            make_site_item(1, stock={"status": "in_stock", "quantity": "124"}),
            make_site_item(2, stock={"status": "out_of_stock", "quantity": None}),
        ],
        [
            make_site_item(3, stock={"status": "untracked", "quantity": None}),
            make_site_item(4, stock={"status": "something_new", "quantity": "5"}),
        ],
    ]

    batches = await batches_of(await site_catalog_source.pull())

    stock = [row for snapshot in batches for row in snapshot.stock]
    assert [(row.product_id, row.warehouse_id, row.quantity) for row in stock] == [
        (make_site_item_id(1), "*", Decimal(124)),
        (make_site_item_id(2), "*", Decimal(0)),
    ]


async def test_a_broken_item_is_skipped_and_the_rest_of_the_page_kept(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """One unreadable card must not stop thousands from updating."""
    fake_site.item_pages = [
        [
            make_site_item(1, name=""),
            make_site_item(2, unit="шт"),
            make_site_item(3),
        ],
    ]

    batches = await batches_of(await site_catalog_source.pull())

    assert [row.id for row in batches[2].products] == [make_site_item_id(3)]


async def test_an_id_seen_earlier_in_the_pass_is_skipped(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """Twice in one INSERT, Postgres refuses the whole page."""
    fake_site.item_pages = [
        [make_site_item(1), make_site_item(1, name="Дубль")],
        [make_site_item(1, name="Ещё дубль"), make_site_item(2)],
    ]

    batches = await batches_of(await site_catalog_source.pull())

    products = [row for snapshot in batches for row in snapshot.products]
    assert [row.name for row in products] == [
        "Потолочный плинтус DD501 DECOR-DIZAYN",
        "Потолочный плинтус DD502 DECOR-DIZAYN",
    ]


async def test_a_pass_with_no_items_is_refused_rather_than_swept(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """An empty listing is a broken site far more often than an empty shop."""
    fake_site.item_pages = [[]]
    pull = await site_catalog_source.pull()

    with pytest.raises(CatalogSourceReadError):
        await batches_of(pull)


@pytest.mark.parametrize("what", ("sections", "price_types"))
async def test_a_pass_with_no_tree_or_no_price_list_is_refused_before_anything(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
    what: str,
) -> None:
    setattr(fake_site, what, [])

    with pytest.raises(CatalogSourceReadError):
        await site_catalog_source.pull()


async def test_a_broken_section_refuses_the_pass(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """A tree placed without one of its nodes puts the children too high."""
    fake_site.sections = [make_site_section(), {"id": "goldy_sec_2"}]

    with pytest.raises(CatalogSourceReadError) as failure:
        await site_catalog_source.pull()

    assert "sections[1]" in str(failure.value)


async def test_a_refused_token_is_a_read_error_the_port_promises(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    fake_site.failures["sections"] = httpx.Response(
        401,
        json={"error": {"code": "unauthorized"}},
    )

    with pytest.raises(CatalogSourceReadError) as failure:
        await site_catalog_source.pull()

    assert isinstance(failure.value, CatalogSourceError)
    assert isinstance(failure.value, InfrastructureError)
    assert "unauthorized" in str(failure.value)


async def test_a_site_that_goes_down_midway_is_unavailable_after_the_first_page(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    """Page one is already imported by then; the pass must not be finalised."""
    fake_site.item_pages = [[make_site_item(1)], [make_site_item(2)]]
    fake_site.failures["items:1"] = httpx.Response(503, json={"error": {"code": "x"}})
    batches = aiter((await site_catalog_source.pull()).batches)
    tree, price_lists, products, prices, stock = [await anext(batches) for _ in range(5)]

    with pytest.raises(CatalogSourceUnavailableError):
        await anext(batches)

    assert len(tree.categories) == len(price_lists.price_types) == 1
    assert [row.id for row in products.products] == [make_site_item_id(1)]
    assert (len(prices.prices), len(stock.stock)) == (1, 1)


@pytest.mark.parametrize(
    "failure",
    (
        httpx.ConnectTimeout("slow"),
        httpx.Response(429, headers={"Retry-After": "5"}),
        httpx.Response(500, text="oops"),
    ),
)
async def test_what_a_later_pass_may_get_past_is_unavailable(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
    failure: httpx.Response | Exception,
) -> None:
    fake_site.failures["price-types"] = failure

    with pytest.raises(CatalogSourceUnavailableError) as raised:
        await site_catalog_source.pull()

    assert isinstance(raised.value, CatalogSourceError)


async def test_a_body_that_is_not_json_is_a_read_error(
    fake_site: FakeSiteCatalog,
    site_catalog_source: SiteCatalogSource,
) -> None:
    fake_site.failures["sections"] = httpx.Response(200, text="<html>maintenance</html>")

    with pytest.raises(CatalogSourceReadError):
        await site_catalog_source.pull()
