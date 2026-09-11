"""Which price list a customer buys at, and what they are then charged.

The binding is keyed by phone number and not by ``user_id``, and it has no
foreign key. That is the decision this file exists to hold down: 1C attaches a
price list to a counterparty, and a counterparty may well not have written to
the bot yet. Keyed by user id, such a message would have nowhere to go and
would be dropped — after which the customer would silently get default prices
forever, because nobody re-sends bindings.

So the test that matters most here is the one where the binding arrives first
and the person registers afterwards. It passes only because resolving a price
list is a join against ``users.phone_number`` made at read time.
"""

from decimal import Decimal

import pytest
from dishka import FromDishka

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.ports.catalog import (
    CatalogScopeKind,
    CatalogSnapshot,
    PricingGateway,
)
from tests.integration.arrange import CommandSender, UserSeeder
from tests.integration.inject import inject
from tests.unit.factories.catalog_factories import (
    BATCH_ID,
    make_binding_row,
    make_price_row,
    make_price_type_row,
    make_product_row,
    make_scope,
    make_snapshot,
)
from tests.unit.factories.domain_factories import CUSTOMER_PHONE, MANAGER_PHONE
from tests.unit.factories.shop_factories import (
    PRICE_TYPE_ID,
    make_price_type_id,
    make_product_id,
)

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

SECOND_BATCH_ID: str = "batch-0002"
RETAIL_PRICE_TYPE_ID: str = "1c-price-type-retail"
EXOTIC_PRICE_TYPE_ID: str = "1c-price-type-exotic"
WHOLESALE_AMOUNT: str = "100.00"
RETAIL_AMOUNT: str = "150.00"
UNBOUND_ACCOUNT_ID: str = "700101"


@inject
async def test_a_bound_customer_buys_at_the_list_the_catalog_gave_them(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    pricing: FromDishka[PricingGateway],
) -> None:
    """The price list and the price, because resolving one is only half the job."""
    seeded = await seed_user(phone_number=CUSTOMER_PHONE)
    await send_worker_command(ImportCatalogCommand(snapshot=_two_price_lists()))

    resolved = await pricing.read_price_type_for(seeded.id)

    assert resolved is not None
    assert resolved.price_type_id == RETAIL_PRICE_TYPE_ID
    [priced] = await pricing.read_priced_products(
        [make_product_id(1)],
        make_price_type_id(resolved.price_type_id),
    )
    assert priced.unit_price is not None
    assert priced.unit_price.amount == Decimal(RETAIL_AMOUNT)


@inject
async def test_a_customer_the_catalog_never_mentioned_buys_at_the_configured_list(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    pricing: FromDishka[PricingGateway],
) -> None:
    """No binding is the ordinary state of a new customer, not a failure."""
    seeded = await seed_user(
        phone_number=MANAGER_PHONE,
        external_id=UNBOUND_ACCOUNT_ID,
    )
    await send_worker_command(ImportCatalogCommand(snapshot=_two_price_lists()))

    resolved = await pricing.read_price_type_for(seeded.id)

    assert resolved is not None
    assert resolved.price_type_id == PRICE_TYPE_ID
    [priced] = await pricing.read_priced_products(
        [make_product_id(1)],
        make_price_type_id(resolved.price_type_id),
    )
    assert priced.unit_price is not None
    assert priced.unit_price.amount == Decimal(WHOLESALE_AMOUNT)


@inject
async def test_a_binding_waits_for_the_person_it_names_to_register(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    pricing: FromDishka[PricingGateway],
) -> None:
    """The whole reason the binding is keyed by phone number.

    1C exports "this counterparty buys at that list" whenever it likes, and the
    person it names may not have written to the bot yet. A row keyed by user id
    would have nowhere to go, the message would be dropped, and nobody re-sends
    bindings — so the customer would sit on default prices forever.
    """
    await send_worker_command(ImportCatalogCommand(snapshot=_two_price_lists()))

    seeded = await seed_user(phone_number=CUSTOMER_PHONE)

    resolved = await pricing.read_price_type_for(seeded.id)
    assert resolved is not None
    assert resolved.price_type_id == RETAIL_PRICE_TYPE_ID


@inject
async def test_a_binding_withdrawn_in_the_source_stops_applying(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    pricing: FromDishka[PricingGateway],
) -> None:
    """Swept like the rest of the projection, which is why the row is batched.

    Were it stamped with an "assigned at" instead, a customer 1C had moved off
    a price list would stay on it for good.
    """
    seeded = await seed_user(phone_number=CUSTOMER_PHONE)
    await send_worker_command(ImportCatalogCommand(snapshot=_two_price_lists()))

    await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.BINDINGS),
        ),
    )

    resolved = await pricing.read_price_type_for(seeded.id)
    assert resolved is not None
    assert resolved.price_type_id == PRICE_TYPE_ID


@inject
async def test_a_price_list_in_a_currency_we_do_not_know_comes_back_marked(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    pricing: FromDishka[PricingGateway],
) -> None:
    """Stored rather than dropped, so the customer gets a refusal and not roubles."""
    seeded = await seed_user(phone_number=CUSTOMER_PHONE)
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                price_types=(make_price_type_row(EXOTIC_PRICE_TYPE_ID, "xts"),),
                bindings=(
                    make_binding_row(
                        phone_number=CUSTOMER_PHONE,
                        price_type_id=EXOTIC_PRICE_TYPE_ID,
                    ),
                ),
            ),
        ),
    )

    resolved = await pricing.read_price_type_for(seeded.id)

    assert resolved is not None
    assert resolved.price_type_id == EXOTIC_PRICE_TYPE_ID
    assert resolved.is_supported is False


@inject
async def test_an_empty_projection_resolves_no_price_list_at_all(
    seed_user: UserSeeder,
    pricing: FromDishka[PricingGateway],
) -> None:
    """A broken snapshot rather than an ordinary absence, and told apart from one."""
    seeded = await seed_user(phone_number=CUSTOMER_PHONE)

    resolved = await pricing.read_price_type_for(seeded.id)

    assert resolved is None


@inject
async def test_a_product_this_list_does_not_price_comes_back_unpriced(
    seed_user: UserSeeder,
    send_worker_command: CommandSender,
    pricing: FromDishka[PricingGateway],
) -> None:
    """Present without a price and absent altogether are two different refusals.

    Collapsing them would turn "we no longer sell this" into "ask a manager
    about the price", which is the wrong thing to tell a customer at checkout.
    """
    await seed_user(phone_number=CUSTOMER_PHONE)
    await send_worker_command(ImportCatalogCommand(snapshot=_two_price_lists()))

    priced = await pricing.read_priced_products(
        [make_product_id(1), make_product_id(2)],
        make_price_type_id(RETAIL_PRICE_TYPE_ID),
    )

    by_id = {row.product_id: row for row in priced}
    assert by_id[make_product_id(1).value].unit_price is not None
    assert by_id[make_product_id(2).value].unit_price is None


def _two_price_lists() -> CatalogSnapshot:
    """Two price lists over one product, and a binding onto the dearer one.

    Product 2 is deliberately priced under neither: "the catalog still holds it
    but this list does not price it" is a state of its own.
    """
    return make_snapshot(
        batch_id=BATCH_ID,
        products=(make_product_row(1), make_product_row(2)),
        price_types=(
            make_price_type_row(),
            make_price_type_row(RETAIL_PRICE_TYPE_ID),
        ),
        prices=(
            make_price_row(1, amount=WHOLESALE_AMOUNT),
            make_price_row(1, amount=RETAIL_AMOUNT, price_type_id=RETAIL_PRICE_TYPE_ID),
        ),
        bindings=(
            make_binding_row(
                phone_number=CUSTOMER_PHONE,
                price_type_id=RETAIL_PRICE_TYPE_ID,
            ),
        ),
    )
