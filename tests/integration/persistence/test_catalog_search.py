"""Finding a product by its name and by a piece of its article.

Two mechanisms answer two different questions and both need Postgres to say
anything at all. Morphology — "дрели" finding "дрель" — is a dictionary, and
the ``russian`` snowball configuration ships with the database. A fragment of
an article, "123" inside "AB-12345", is something no dictionary can do: that is
trigrams, which also buy tolerance of a missing letter.

The first test here is not about searching. The normalisation rule exists twice
— as the SQL of a generated column and as a Python function that prepares the
term before it is bound — and the pair is what makes them agree. Drift between
them would be silent: search would simply stop finding some articles, and no
unit test could notice, because only the database computes one of the two.
"""

import pytest
from dishka import FromDishka
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.ports.catalog import (
    CatalogQueryGateway,
    CatalogScopeKind,
    CatalogSnapshot,
    ProductRow,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.search_term import SearchTerm
from goldy.application.common.views.catalog import ProductSearchView
from goldy.infrastructure.persistence.models import normalize_name, normalize_sku
from tests.integration.arrange import CommandSender
from tests.integration.inject import inject
from tests.unit.factories.catalog_factories import (
    SOURCE_CHANGED_AT,
    make_scope,
    make_snapshot,
)
from tests.unit.factories.shop_factories import (
    PRICE_TYPE_ID,
    UNIT_NAME,
    make_price_type_id,
    make_product_id,
)

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

SECOND_BATCH_ID: str = "batch-0002"
NORMALIZED_COLUMNS_SQL: str = (
    "SELECT sku, name, sku_normalized, name_normalized FROM catalog_products"
)

DRILL: int = 1
TREE: int = 2
SCREWDRIVER: int = 3

AWKWARD: tuple[tuple[str, str], ...] = (
    ("AB-123", "Ёлка"),
    ("ab 123", "ЁЛКА"),
    ("ab123", "елка"),
    ("AB_123", "Дрель Ёршик"),
    ("AB.123", "дрель ёршик"),
    ("ab/123", "ЁЖ"),
)
"""How an article is actually typed, and the two spellings of the Russian "yo"."""


@inject
async def test_the_database_normalises_exactly_as_python_does(
    send_worker_command: CommandSender,
    engine: AsyncEngine,
) -> None:
    """The one test holding the duplicated normalisation rule together.

    Read straight out of the generated columns rather than through the gateway,
    because what is under test is what Postgres computed — a search that went
    through the port would compare the rule against itself.
    """
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                products=tuple(
                    _a_product(index, name=name, sku=sku)
                    for index, (sku, name) in enumerate(AWKWARD, start=1)
                ),
            ),
        ),
    )

    async with engine.connect() as connection:
        rows = (await connection.execute(text(NORMALIZED_COLUMNS_SQL))).all()

    assert len(rows) == len(AWKWARD)
    assert [(row.sku_normalized, row.name_normalized) for row in rows] == [
        (normalize_sku(row.sku), normalize_name(row.name)) for row in rows
    ]


@inject
async def test_a_name_is_found_through_its_morphology(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """A plural finds the singular, and only a dictionary knows that it does."""
    await send_worker_command(ImportCatalogCommand(snapshot=_a_workshop()))

    found = await _search(catalog, "дрели")

    assert [product.id for product in found.products] == [make_product_id(DRILL).value]


@inject
async def test_a_name_is_found_whichever_way_the_russian_yo_is_spelled(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """Nobody types the dotted letter, and snowball leaves the two apart."""
    await send_worker_command(ImportCatalogCommand(snapshot=_a_workshop()))

    dotted = await _search(catalog, "ёлка")
    plain = await _search(catalog, "елка")

    assert [product.id for product in dotted.products] == [make_product_id(TREE).value]
    assert [product.id for product in plain.products] == [make_product_id(TREE).value]


@inject
async def test_a_fragment_of_an_article_finds_the_product(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """What trigrams are here for — no dictionary matches "12345" to "AB-12345"."""
    await send_worker_command(ImportCatalogCommand(snapshot=_a_workshop()))

    found = await _search(catalog, "12345")

    assert [product.id for product in found.products] == [make_product_id(DRILL).value]
    assert found.exact_sku_product_id is None


@inject
async def test_an_article_is_found_however_its_separators_are_typed(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """One article to everybody except a database: AB-123, ab 123 and ab123."""
    await send_worker_command(ImportCatalogCommand(snapshot=_a_workshop()))

    hyphenated = await _search(catalog, "AB-123")
    spaced = await _search(catalog, "ab 123")
    bare = await _search(catalog, "ab123")

    assert hyphenated.exact_sku_product_id == make_product_id(SCREWDRIVER).value
    assert spaced.exact_sku_product_id == make_product_id(SCREWDRIVER).value
    assert bare.exact_sku_product_id == make_product_id(SCREWDRIVER).value


@inject
async def test_an_article_naming_one_product_offers_its_card(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """The single case where opening the card straight away is safe.

    The fragment "AB123" also matches the drill, whose article merely starts
    with it, so the shortcut has to come from an exact match and not from the
    result being short.
    """
    await send_worker_command(ImportCatalogCommand(snapshot=_a_workshop()))

    found = await _search(catalog, "ab123")

    assert found.exact_sku_product_id == make_product_id(SCREWDRIVER).value
    assert len(found.products) > 1


@inject
async def test_an_article_two_products_share_offers_no_card(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """1C does not keep articles unique, so "exactly one" has to be checked."""
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                products=(
                    _a_product(DRILL, name="Дрель ударная", sku="AB-123"),
                    _a_product(TREE, name="Ёлка новогодняя", sku="ab 123"),
                ),
            ),
        ),
    )

    found = await _search(catalog, "ab123")

    assert found.total == 2
    assert found.exact_sku_product_id is None


@inject
async def test_a_term_the_catalog_answers_nothing_to_is_an_empty_page(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """A screen of its own rather than an error — people mistype and search again."""
    await send_worker_command(ImportCatalogCommand(snapshot=_a_workshop()))

    found = await _search(catalog, "фотоаппарат")

    assert found.is_empty
    assert found.total == 0
    assert found.exact_sku_product_id is None


@inject
async def test_a_withdrawn_product_is_not_searched_for(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """The search indexes are partial on ``is_active``, and so is the predicate."""
    await send_worker_command(ImportCatalogCommand(snapshot=_a_workshop()))
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                batch_id=SECOND_BATCH_ID,
                products=(_a_product(TREE, name="Ёлка новогодняя", sku="XY-77"),),
            ),
        ),
    )

    await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRODUCTS),
        ),
    )

    found = await _search(catalog, "дрели")
    assert found.is_empty


def _a_workshop() -> CatalogSnapshot:
    """Three products: two articles that overlap and three names that do not."""
    return make_snapshot(
        products=(
            _a_product(DRILL, name="Дрель ударная Bosch", sku="AB-12345"),
            _a_product(TREE, name="Ёлка новогодняя", sku="XY-77"),
            _a_product(SCREWDRIVER, name="Шуруповёрт аккумуляторный", sku="AB-123"),
        ),
    )


def _a_product(index: int, name: str, sku: str | None) -> ProductRow:
    return ProductRow(
        id=make_product_id(index).value,
        sku=sku,
        name=name,
        unit_name=UNIT_NAME,
        source_changed_at=SOURCE_CHANGED_AT,
    )


async def _search(catalog: CatalogQueryGateway, term: str) -> ProductSearchView:
    return await catalog.search_products(
        term=SearchTerm(value=term),
        price_type_id=make_price_type_id(PRICE_TYPE_ID),
        pagination=Pagination(),
    )
