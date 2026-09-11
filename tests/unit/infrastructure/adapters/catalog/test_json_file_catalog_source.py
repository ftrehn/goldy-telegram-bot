"""What the seeder makes of the file it was pointed at.

The adapter is a parser, which makes it the one piece of this wave that can be
exercised end to end without a database. Two things are worth pinning. The
first is the decisions: an absent collection is an empty one, a number goes
through its text so no binary float reaches a price, and a unit ratio nobody
sent is one. The second is the promise every adapter makes — that no library
exception escapes it — because a seeder is run by a person reading the output,
and ``JSONDecodeError`` in a traceback is not an answer to "what is wrong with
my fixture".
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from goldy.application.common.ports.catalog import CatalogScopeKind
from goldy.application.error import CatalogSourceError
from goldy.infrastructure.adapters.catalog.json_file_catalog_source import (
    JsonFileCatalogSource,
)
from goldy.infrastructure.errors import CatalogSourceReadError, InfrastructureError

MINIMAL: Final[str] = json.dumps({
    "batch_id": "seed-0001",
    "scope": {"kind": "products"},
    "products": [
        {
            "id": "1c-product-1",
            "sku": "AB-12345",
            "name": "Болт оцинкованный",
            "unit_name": "шт",
            "unit_ratio": "0.1",
            "source_changed_at": "2026-09-10T09:00:00+03:00",
        },
    ],
})


def _write(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _source(tmp_path: Path, document: object) -> JsonFileCatalogSource:
    return JsonFileCatalogSource(_write(tmp_path, document))


async def test_a_snapshot_arrives_with_its_batch_and_its_scope(
    tmp_path: Path,
) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text(MINIMAL, encoding="utf-8")

    snapshot = await JsonFileCatalogSource(path).read_snapshot()

    assert snapshot.batch_id == "seed-0001"
    assert snapshot.scope.kind is CatalogScopeKind.PRODUCTS
    assert len(snapshot.products) == 1
    assert snapshot.products[0].sku == "AB-12345"


async def test_a_collection_the_batch_does_not_carry_is_empty_rather_than_missing(
    tmp_path: Path,
) -> None:
    """A price batch carries no categories, and must not have to say so.

    Demanding an empty list of every kind would make every fixture six keys
    long in order to say nothing five times.
    """
    path = tmp_path / "snapshot.json"
    path.write_text(MINIMAL, encoding="utf-8")

    snapshot = await JsonFileCatalogSource(path).read_snapshot()

    assert snapshot.categories == ()
    assert snapshot.prices == ()
    assert snapshot.price_type_bindings == ()


async def test_an_amount_is_read_through_its_text_so_no_float_reaches_a_price(
    tmp_path: Path,
) -> None:
    """``0.1`` in JSON is a binary float and is not one tenth.

    A price that went through a float would be a few kopecks out by the time it
    was frozen onto an order line, and the line is what somebody is invoiced
    against.
    """
    source = _source(
        tmp_path,
        {
            "batch_id": "seed-0001",
            "scope": {"kind": "prices", "price_type_id": "1c-price-type-wholesale"},
            "prices": [
                {
                    "product_id": "1c-product-1",
                    "price_type_id": "1c-price-type-wholesale",
                    "amount": 0.1,
                    "currency": "RUB",
                },
            ],
        },
    )

    snapshot = await source.read_snapshot()

    assert snapshot.prices[0].amount == Decimal("0.1")
    assert snapshot.scope.price_type_id == "1c-price-type-wholesale"


async def test_a_product_without_a_ratio_is_sold_one_for_one(tmp_path: Path) -> None:
    source = _source(
        tmp_path,
        {
            "batch_id": "seed-0001",
            "scope": {"kind": "products"},
            "products": [
                {
                    "id": "1c-product-1",
                    "sku": None,
                    "name": "Гайка оцинкованная",
                    "unit_name": "шт",
                },
            ],
        },
    )

    snapshot = await source.read_snapshot()

    assert snapshot.products[0].unit_ratio == Decimal(1)
    assert snapshot.products[0].sku is None


async def test_a_missing_file_is_reported_rather_than_raised_as_an_oserror(
    tmp_path: Path,
) -> None:
    """The adapter's promise: no library exception leaves it, ever."""
    source = JsonFileCatalogSource(tmp_path / "nothing-here.json")

    with pytest.raises(CatalogSourceReadError) as failure:
        await source.read_snapshot()

    assert "nothing-here.json" in str(failure.value)
    assert isinstance(failure.value.__cause__, OSError)


async def test_a_file_that_is_not_json_names_itself_as_such(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text("{ this is not json", encoding="utf-8")

    with pytest.raises(CatalogSourceReadError) as failure:
        await JsonFileCatalogSource(path).read_snapshot()

    assert "not valid JSON" in str(failure.value)


async def test_a_file_that_is_not_utf_eight_is_reported_as_such(tmp_path: Path) -> None:
    """A fixture saved out of 1C in its own code page, which happens."""
    path = tmp_path / "snapshot.json"
    path.write_bytes('{"batch_id": "Болт"}'.encode("cp1251"))

    with pytest.raises(CatalogSourceReadError) as failure:
        await JsonFileCatalogSource(path).read_snapshot()

    assert "not valid UTF-8" in str(failure.value)
    assert isinstance(failure.value.__cause__, UnicodeDecodeError)


async def test_a_wrong_field_is_named_by_the_path_it_sits_at(tmp_path: Path) -> None:
    """Naming the field is the point of hand-writing the whole parser.

    A seeder is run by a person watching the output, and naming the field is
    the difference between fixing a fixture and guessing at it.
    """
    source = _source(
        tmp_path,
        {
            "batch_id": "seed-0001",
            "scope": {"kind": "products"},
            "products": [
                {"id": "1c-product-1", "sku": None, "name": "Болт", "unit_name": "шт"},
                {"id": "1c-product-2", "sku": None, "name": 42, "unit_name": "шт"},
            ],
        },
    )

    with pytest.raises(CatalogSourceReadError) as failure:
        await source.read_snapshot()

    assert "products[1].name" in str(failure.value)
    assert "int" in str(failure.value)


async def test_an_empty_string_is_not_a_name(tmp_path: Path) -> None:
    """Blank is missing spelled differently, and only one of them gets handled."""
    source = _source(
        tmp_path,
        {
            "batch_id": "seed-0001",
            "scope": {"kind": "products"},
            "products": [
                {"id": "1c-product-1", "sku": None, "name": "   ", "unit_name": "шт"},
            ],
        },
    )

    with pytest.raises(CatalogSourceReadError) as failure:
        await source.read_snapshot()

    assert "products[0].name" in str(failure.value)


async def test_a_scope_nobody_can_sweep_is_refused_with_the_kinds_listed(
    tmp_path: Path,
) -> None:
    """A typo in the scope would otherwise sweep the wrong part of the catalog."""
    source = _source(
        tmp_path,
        {"batch_id": "seed-0001", "scope": {"kind": "productz"}},
    )

    with pytest.raises(CatalogSourceReadError) as failure:
        await source.read_snapshot()

    assert "productz" in str(failure.value)
    assert "price_types" in str(failure.value)


async def test_a_moment_that_is_not_a_moment_is_refused(tmp_path: Path) -> None:
    """``source_changed_at`` decides which of two deliveries wins.

    A string that is not a date would be dropped to ``None``, and a row with no
    moment is taken as the newer one — so a malformed fixture would overwrite
    a fresh price with a stale one and mark itself fresh.
    """
    source = _source(
        tmp_path,
        {
            "batch_id": "seed-0001",
            "scope": {"kind": "products"},
            "products": [
                {
                    "id": "1c-product-1",
                    "sku": None,
                    "name": "Болт",
                    "unit_name": "шт",
                    "source_changed_at": "yesterday",
                },
            ],
        },
    )

    with pytest.raises(CatalogSourceReadError) as failure:
        await source.read_snapshot()

    assert "products[0].source_changed_at" in str(failure.value)


async def test_a_boolean_is_not_a_number_even_though_python_adds_it_up(
    tmp_path: Path,
) -> None:
    """``True`` is an ``int`` in Python, and a quantity of ``True`` is nonsense."""
    source = _source(
        tmp_path,
        {
            "batch_id": "seed-0001",
            "scope": {"kind": "stock", "warehouse_id": "*"},
            "stock": [
                {"product_id": "1c-product-1", "warehouse_id": "*", "quantity": True},
            ],
        },
    )

    with pytest.raises(CatalogSourceReadError) as failure:
        await source.read_snapshot()

    assert "stock[0].quantity" in str(failure.value)


async def test_a_list_where_an_object_belongs_is_refused_by_shape(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path, ["not", "a", "snapshot"])

    with pytest.raises(CatalogSourceReadError) as failure:
        await source.read_snapshot()

    assert "the snapshot" in str(failure.value)


def test_the_read_error_answers_to_both_names_it_promises() -> None:
    """Two parents, and neither is decorative.

    It is an infrastructure error because a missing file is a failure of an
    adapter, and a ``CatalogSourceError`` because that is what the port
    documents — a seeder catching the documented error has to catch this one.
    """
    failure = CatalogSourceReadError("broken")

    assert isinstance(failure, InfrastructureError)
    assert isinstance(failure, CatalogSourceError)
