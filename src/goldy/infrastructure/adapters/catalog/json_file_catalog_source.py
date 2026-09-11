import asyncio
import json
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, override

from goldy.application.common.ports.catalog import (
    CatalogScope,
    CatalogScopeKind,
    CatalogSnapshot,
    CatalogSource,
    CategoryRow,
    PriceRow,
    PriceTypeBindingRow,
    PriceTypeRow,
    ProductRow,
    StockRow,
)
from goldy.infrastructure.errors import CatalogSourceReadError

logger: Final[logging.Logger] = logging.getLogger(__name__)


class JsonFileCatalogSource(CatalogSource):
    """Reads one catalog batch out of a JSON file.

    The seeder's source and nothing more. The RabbitMQ consumer that replaces
    it pushes rather than pulls and will not implement this port at all — the
    seam of the integration is ``ImportCatalogCommand``, which both of them
    send.

    The path arrives in the constructor as request-scoped context, because it
    comes from ``--file`` on the command line and belongs to one run rather
    than to the process. A config would make it a property of the bot, and the
    bot never reads a catalog file.

    Every failure of the file and of its shape leaves here as
    :class:`CatalogSourceReadError`, naming the field that was wrong. A seeder
    is run by a person watching the output, and "expected a string at
    products[7].name" is the difference between fixing a fixture and guessing
    at it.
    """

    def __init__(self, path: Path) -> None:
        self._path: Final[Path] = path

    @override
    async def read_snapshot(self) -> CatalogSnapshot:
        document = _parse(await self._read())
        root = _as_mapping(document, "the snapshot")

        snapshot = CatalogSnapshot(
            batch_id=_as_text(root.get("batch_id"), "batch_id"),
            scope=_as_scope(root.get("scope")),
            categories=tuple(
                _as_category_row(item, index)
                for index, item in enumerate(
                    _as_list(root.get("categories"), "categories")
                )
            ),
            products=tuple(
                _as_product_row(item, index)
                for index, item in enumerate(_as_list(root.get("products"), "products"))
            ),
            price_types=tuple(
                _as_price_type_row(item, index)
                for index, item in enumerate(
                    _as_list(root.get("price_types"), "price_types"),
                )
            ),
            prices=tuple(
                _as_price_row(item, index)
                for index, item in enumerate(_as_list(root.get("prices"), "prices"))
            ),
            stock=tuple(
                _as_stock_row(item, index)
                for index, item in enumerate(_as_list(root.get("stock"), "stock"))
            ),
            price_type_bindings=tuple(
                _as_binding_row(item, index)
                for index, item in enumerate(
                    _as_list(root.get("price_type_bindings"), "price_type_bindings"),
                )
            ),
        )

        logger.info(
            "json_file_catalog_source: file=%s batch=%s categories=%d products=%d",
            self._path,
            snapshot.batch_id,
            len(snapshot.categories),
            len(snapshot.products),
        )

        return snapshot

    async def _read(self) -> str:
        """Reads the file off the event loop, since a fixture can be large.

        Raises:
            CatalogSourceReadError: the file is missing, unreadable, or not
                text this service can decode.
        """
        try:
            return await asyncio.to_thread(self._path.read_text, encoding="utf-8")
        except OSError as e:
            logger.exception("failed to read the catalog file")
            msg = f"Cannot read the catalog snapshot at '{self._path}'."
            raise CatalogSourceReadError(msg) from e
        except UnicodeDecodeError as e:
            logger.exception("failed to decode the catalog file")
            msg = f"The catalog snapshot at '{self._path}' is not valid UTF-8."
            raise CatalogSourceReadError(msg) from e


def _parse(text: str) -> object:
    """Turns the text of the file into whatever JSON it spells.

    Raises:
        CatalogSourceReadError: the file is not JSON at all.
    """
    try:
        return json.loads(text)
    except ValueError as e:
        msg = f"The catalog snapshot is not valid JSON: {e}."
        raise CatalogSourceReadError(msg) from e


def _as_scope(value: object) -> CatalogScope:
    """Reads what this batch covers, and therefore what finalising it may sweep.

    The qualifiers are optional here and meaningful only for their own kinds: a
    price export names the price list it carried, a stock export names the
    warehouse, and nothing else names anything.
    """
    scope = _as_mapping(value, "scope")
    kind = _as_text(scope.get("kind"), "scope.kind")

    try:
        return CatalogScope(
            kind=CatalogScopeKind(kind),
            price_type_id=_as_optional_text(
                scope.get("price_type_id"),
                "scope.price_type_id",
            ),
            warehouse_id=_as_optional_text(
                scope.get("warehouse_id"),
                "scope.warehouse_id",
            ),
        )
    except ValueError as e:
        known = ", ".join(member.value for member in CatalogScopeKind)
        msg = f"Unknown scope kind '{kind}' at scope.kind; expected one of {known}."
        raise CatalogSourceReadError(msg) from e


def _as_category_row(value: object, index: int) -> CategoryRow:
    where = f"categories[{index}]"
    item = _as_mapping(value, where)

    return CategoryRow(
        id=_as_text(item.get("id"), f"{where}.id"),
        parent_id=_as_optional_text(item.get("parent_id"), f"{where}.parent_id"),
        name=_as_text(item.get("name"), f"{where}.name"),
        source_changed_at=_as_optional_moment(
            item.get("source_changed_at"),
            f"{where}.source_changed_at",
        ),
    )


def _as_product_row(value: object, index: int) -> ProductRow:
    where = f"products[{index}]"
    item = _as_mapping(value, where)

    return ProductRow(
        id=_as_text(item.get("id"), f"{where}.id"),
        sku=_as_optional_text(item.get("sku"), f"{where}.sku"),
        name=_as_text(item.get("name"), f"{where}.name"),
        full_name=_as_optional_text(item.get("full_name"), f"{where}.full_name"),
        category_id=_as_optional_text(item.get("category_id"), f"{where}.category_id"),
        unit_id=_as_optional_text(item.get("unit_id"), f"{where}.unit_id"),
        unit_name=_as_text(item.get("unit_name"), f"{where}.unit_name"),
        unit_ratio=_as_amount(item.get("unit_ratio"), f"{where}.unit_ratio", Decimal(1)),
        description=_as_optional_text(item.get("description"), f"{where}.description"),
        image_url=_as_optional_text(item.get("image_url"), f"{where}.image_url"),
        source_changed_at=_as_optional_moment(
            item.get("source_changed_at"),
            f"{where}.source_changed_at",
        ),
    )


def _as_price_type_row(value: object, index: int) -> PriceTypeRow:
    where = f"price_types[{index}]"
    item = _as_mapping(value, where)

    return PriceTypeRow(
        id=_as_text(item.get("id"), f"{where}.id"),
        name=_as_text(item.get("name"), f"{where}.name"),
        currency=_as_text(item.get("currency"), f"{where}.currency"),
        source_changed_at=_as_optional_moment(
            item.get("source_changed_at"),
            f"{where}.source_changed_at",
        ),
    )


def _as_price_row(value: object, index: int) -> PriceRow:
    where = f"prices[{index}]"
    item = _as_mapping(value, where)

    return PriceRow(
        product_id=_as_text(item.get("product_id"), f"{where}.product_id"),
        price_type_id=_as_text(item.get("price_type_id"), f"{where}.price_type_id"),
        amount=_as_amount(item.get("amount"), f"{where}.amount", None),
        currency=_as_text(item.get("currency"), f"{where}.currency"),
        source_changed_at=_as_optional_moment(
            item.get("source_changed_at"),
            f"{where}.source_changed_at",
        ),
    )


def _as_stock_row(value: object, index: int) -> StockRow:
    where = f"stock[{index}]"
    item = _as_mapping(value, where)

    return StockRow(
        product_id=_as_text(item.get("product_id"), f"{where}.product_id"),
        warehouse_id=_as_text(item.get("warehouse_id"), f"{where}.warehouse_id"),
        quantity=_as_amount(item.get("quantity"), f"{where}.quantity", None),
        source_changed_at=_as_optional_moment(
            item.get("source_changed_at"),
            f"{where}.source_changed_at",
        ),
    )


def _as_binding_row(value: object, index: int) -> PriceTypeBindingRow:
    where = f"price_type_bindings[{index}]"
    item = _as_mapping(value, where)

    return PriceTypeBindingRow(
        phone_number=_as_text(item.get("phone_number"), f"{where}.phone_number"),
        price_type_id=_as_text(item.get("price_type_id"), f"{where}.price_type_id"),
        source_counterparty_id=_as_optional_text(
            item.get("source_counterparty_id"),
            f"{where}.source_counterparty_id",
        ),
        source_changed_at=_as_optional_moment(
            item.get("source_changed_at"),
            f"{where}.source_changed_at",
        ),
    )


def _as_mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        msg = f"Expected an object at {where}, got {_name_of(value)}."
        raise CatalogSourceReadError(msg)

    return value


def _as_list(value: object, where: str) -> Sequence[object]:
    """A collection the snapshot may simply not carry.

    Absent and empty mean the same thing here, deliberately. A batch of prices
    carries no categories, and demanding an empty list of every kind would make
    every fixture six keys long to say nothing five times.
    """
    if value is None:
        return ()

    if not isinstance(value, list):
        msg = f"Expected a list at {where}, got {_name_of(value)}."
        raise CatalogSourceReadError(msg)

    return value


def _as_text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        msg = f"Expected a non-empty string at {where}, got {_name_of(value)}."
        raise CatalogSourceReadError(msg)

    return value


def _as_optional_text(value: object, where: str) -> str | None:
    if value is None:
        return None

    return _as_text(value, where)


def _as_amount(value: object, where: str, default: Decimal | None) -> Decimal:
    """A number read through its text, so no binary float reaches a price.

    ``0.1`` in JSON is a binary float and is not one tenth. Going through
    ``str`` first is what keeps the kopecks the fixture spells the ones the
    projection stores.
    """
    if value is None and default is not None:
        return default

    if isinstance(value, bool) or not isinstance(value, str | int | float):
        msg = f"Expected a number at {where}, got {_name_of(value)}."
        raise CatalogSourceReadError(msg)

    try:
        return Decimal(str(value))
    except InvalidOperation as e:
        msg = f"Expected a number at {where}, got '{value}'."
        raise CatalogSourceReadError(msg) from e


def _as_optional_moment(value: object, where: str) -> datetime | None:
    """When 1C last changed the object, as an ISO 8601 moment.

    Optional, because today a fixture fills it by hand. What it is for is the
    conditional upsert: without it a redelivered old message cannot be told
    from a new one, and it would overwrite a fresh price with a stale one.
    """
    if value is None:
        return None

    text = _as_text(value, where)

    try:
        return datetime.fromisoformat(text)
    except ValueError as e:
        msg = f"Expected an ISO 8601 moment at {where}, got '{text}'."
        raise CatalogSourceReadError(msg) from e


def _name_of(value: object) -> str:
    return "null" if value is None else type(value).__name__
