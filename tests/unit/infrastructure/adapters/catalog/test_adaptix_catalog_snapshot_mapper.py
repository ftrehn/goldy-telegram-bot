"""What the mapper makes of a scope handed to it on its own.

A finalisation body carries nothing but a scope, and the receiver hands the
mapper the value under ``scope`` rather than the body around it. Two things
are worth pinning: that the scope is read by the same rules a snapshot's is
— the same retort, the same refusal of a kind nobody can sweep — and that a
refusal still names the field from the key the reader of the body would look
under, so ``scope.kind`` and not a bare ``kind``.
"""

import pytest

from goldy.application.common.ports.catalog import CatalogScope, CatalogScopeKind
from goldy.infrastructure.adapters.catalog.adaptix_catalog_snapshot_mapper import (
    AdaptixCatalogSnapshotMapper,
)
from goldy.infrastructure.errors import CatalogSourceReadError


def test_a_scope_arrives_with_its_kind_and_its_qualifier() -> None:
    mapper = AdaptixCatalogSnapshotMapper()

    scope = mapper.to_scope({"kind": "prices", "price_type_id": "pt-wholesale"})

    assert scope == CatalogScope(
        kind=CatalogScopeKind.PRICES,
        price_type_id="pt-wholesale",
    )


def test_a_scope_without_a_qualifier_leaves_both_unset() -> None:
    """``{"kind": "categories"}`` is the whole finalisation body 1C sends for groups."""
    mapper = AdaptixCatalogSnapshotMapper()

    scope = mapper.to_scope({"kind": "categories"})

    assert scope.kind is CatalogScopeKind.CATEGORIES
    assert scope.price_type_id is None
    assert scope.warehouse_id is None


def test_a_kind_nobody_can_sweep_is_named_under_the_scope_key() -> None:
    """The detail reaches the 1C event log, and ``scope.kind`` is where to look."""
    mapper = AdaptixCatalogSnapshotMapper()

    with pytest.raises(CatalogSourceReadError) as failure:
        mapper.to_scope({"kind": "pricez"})

    assert "scope.kind" in str(failure.value)
    assert "pricez" in str(failure.value)
    assert "price_types" in str(failure.value)


def test_a_scope_that_is_not_an_object_is_refused_by_shape() -> None:
    mapper = AdaptixCatalogSnapshotMapper()

    with pytest.raises(CatalogSourceReadError) as failure:
        mapper.to_scope("prices")

    assert "scope:" in str(failure.value)


def test_a_scope_without_a_kind_is_refused() -> None:
    mapper = AdaptixCatalogSnapshotMapper()

    with pytest.raises(CatalogSourceReadError) as failure:
        mapper.to_scope({"price_type_id": "pt-wholesale"})

    assert "scope" in str(failure.value)
    assert "kind" in str(failure.value)
