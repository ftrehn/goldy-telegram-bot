"""Builders for the site's catalog JSON and for a client pointed at a fake site.

The item shape is the one the site's ``docs/API.md`` documents for
``GET /catalog/items``; a test overrides the one field it is about. Ids follow
the site's convention — a GUID-like string for an item 1C manages — and each
item has its own ``site_id`` so a fallback article is recognisable.
"""

import httpx

from goldy.infrastructure.adapters.site_api.site_api_client import SiteApiClient

SITE_API_BASE_URL: str = "https://tkgoldy.ru/api/v1/"
SITE_API_TOKEN: str = "tkg_3f9a0c1e_test"
SITE_PRICE_TYPE_ID: str = "BASE"


def make_site_api_client(transport: httpx.AsyncBaseTransport) -> SiteApiClient:
    """A client over *transport*, configured the way the provider builds one."""
    http_client = httpx.AsyncClient(
        base_url=SITE_API_BASE_URL,
        transport=transport,
        follow_redirects=False,
    )
    return SiteApiClient(http_client, SITE_API_TOKEN)


def make_site_item_id(index: int = 1) -> str:
    return f"8d1f0000-0000-0000-0000-{index:012d}"


def make_site_section(
    section_id: str = "goldy_sec_12",
    parent_id: str | None = None,
    name: str = "Потолочный плинтус",
) -> dict[str, object]:
    return {
        "id": section_id,
        "site_id": 12,
        "parent_id": parent_id,
        "name": name,
        "code": "potolochnye_plintusa",
        "sort": 100,
        "depth": 1,
    }


def make_site_price_type(
    price_type_id: str = SITE_PRICE_TYPE_ID,
    currency: str = "RUB",
) -> dict[str, object]:
    return {"id": price_type_id, "name": "Розничная", "currency": currency}


def make_site_item(index: int = 1, **overrides: object) -> dict[str, object]:
    """One sellable row, in stock and priced; override any top-level field."""
    item_id = make_site_item_id(index)
    return {
        "id": item_id,
        "site_id": 6000 + index,
        "group_id": item_id,
        "sku": f"DD{500 + index}",
        "name": f"Потолочный плинтус DD{500 + index} DECOR-DIZAYN",
        "variant": None,
        "section_id": "goldy_sec_12",
        "brand_id": "decor-dizayn",
        "unit": {"code": "796", "name": "шт"},
        "ratio": "1",
        "description": "Плинтус из полистирола",
        "images": [f"https://tkgoldy.ru/upload/iblock/{index}.jpg"],
        "url": f"https://tkgoldy.ru/catalog/potolochnye_plintusa/dd{500 + index}/",
        "price": {
            "price_type_id": SITE_PRICE_TYPE_ID,
            "amount": "412.00",
            "currency": "RUB",
        },
        "stock": {"status": "in_stock", "quantity": "124"},
        "managed_by_1c": True,
    } | overrides
