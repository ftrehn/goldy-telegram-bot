"""The one HTTP client the bot talks to the site tkgoldy.ru through.

The site is the only bridge to 1C (ADR-0004) and its contract is the site
repository's ``docs/API.md``. This module knows that contract's transport half
— the Bearer token, ``X-Request-Id``, the ``data``/``meta``/``error`` envelope,
the cursor — and nothing about what any endpoint means. The catalog source is
built on it today; the order outbox and linking will be built on it next, and
none of them should have to learn httpx.
"""

import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Final
from uuid import uuid4

import httpx

from goldy.infrastructure.errors import (
    SiteApiError,
    SiteApiRejectedError,
    SiteApiResponseError,
    SiteApiUnavailableError,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

REQUEST_ID_HEADER: Final[str] = "X-Request-Id"
CUSTOMER_HEADER: Final[str] = "X-Customer"


@dataclass(frozen=True, slots=True)
class SiteApiResponse:
    """One successful answer, unwrapped from the envelope.

    ``data`` is whatever JSON the endpoint returns there — a list, an object,
    ``None`` for a 204 — and deciding what it means is the caller's job.
    ``request_id`` is the one the site echoed back, so a log line on this side
    finds its twin on the other.
    """

    data: object
    meta: Mapping[str, object]
    request_id: str


class SiteApiClient:
    """Sends authenticated requests to the site API and reads its envelope.

    **No library exception leaves this class.** Every httpx failure, every
    status the contract gives meaning to and every body that is not the
    contract is turned into a :class:`SiteApiError` subclass, split by what a
    caller can do about it:

    - :class:`SiteApiUnavailableError` — timeout, refused connection, 429 or
      5xx. Worth another attempt later; ``retry_after`` when the site said.
    - :class:`SiteApiRejectedError` — every other 4xx. The same request gets
      the same refusal, so retrying it only fills the site's log.
    - :class:`SiteApiResponseError` — a 2xx whose body is not the envelope, or
      a redirect. A defect on one side or the other.

    The ``httpx.AsyncClient`` arrives built — base URL, timeout, no redirect
    following — because its lifetime belongs to the process and its settings
    to the composition root. The token arrives as a string and is added to
    each request here, so the header's name and scheme are stated once, next
    to the code that relies on them.
    """

    def __init__(self, http_client: httpx.AsyncClient, token: str) -> None:
        self._http: Final[httpx.AsyncClient] = http_client
        self._token: Final[str] = token

    async def get(
        self,
        path: str,
        params: Mapping[str, str | int] | None = None,
        *,
        customer: str | None = None,
    ) -> SiteApiResponse:
        """One GET, relative to the API root.

        Raises:
            SiteApiError: in one of the three flavours listed on the class.
        """
        return await self.request("GET", path, params=params, customer=customer)

    async def post(
        self,
        path: str,
        body: Mapping[str, object],
        *,
        customer: str | None = None,
    ) -> SiteApiResponse:
        """One POST with a JSON body, relative to the API root.

        Raises:
            SiteApiError: in one of the three flavours listed on the class.
        """
        return await self.request("POST", path, body=body, customer=customer)

    async def delete(self, path: str) -> SiteApiResponse:
        """One DELETE, relative to the API root.

        Raises:
            SiteApiError: in one of the three flavours listed on the class.
        """
        return await self.request("DELETE", path)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        body: Mapping[str, object] | None = None,
        customer: str | None = None,
    ) -> SiteApiResponse:
        """One request of any method, relative to the API root.

        ``customer`` becomes ``X-Customer`` — the subject of a person the site
        has linked to one of its customers — and is left off entirely when
        there is none: a request without it is the guest storefront, which is
        a different answer, not the same one for nobody in particular.

        Raises:
            SiteApiError: in one of the three flavours listed on the class.
        """
        request_id = uuid4().hex
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            REQUEST_ID_HEADER: request_id,
        }
        if customer is not None:
            headers[CUSTOMER_HEADER] = customer

        where = f"{method} {path}"

        try:
            response = await self._http.request(
                method,
                path,
                params=params,
                json=body,
                headers=headers,
            )
        except httpx.TimeoutException as e:
            msg = f"The site API did not answer {where} in time."
            raise SiteApiUnavailableError(msg, request_id=request_id) from e
        except httpx.HTTPError as e:
            msg = f"The site API could not be reached for {where}: {e}."
            raise SiteApiUnavailableError(msg, request_id=request_id) from e
        except httpx.InvalidURL as e:
            msg = f"{where} does not make a valid site API address: {e}."
            raise SiteApiError(msg, request_id=request_id) from e

        return _read(response, where, request_id)

    async def paginate(
        self,
        path: str,
        *,
        limit: int,
        params: Mapping[str, str | int] | None = None,
        customer: str | None = None,
    ) -> AsyncIterator[SiteApiResponse]:
        """Every page of a cursor listing, fetched as the caller asks for it.

        Follows ``meta.next_cursor`` until it is ``null``. ``params`` go on the
        first request only: the site's cursor already remembers the listing it
        was cut from, and repeating a filter beside it is at best redundant and
        at worst a different listing. A cursor the site
        hands back twice is refused rather than followed, because following it
        is a loop that never ends and imports the same page forever.

        Raises:
            SiteApiError: a page failed, or the cursor is not the contract.
        """
        cursor: str | None = None
        seen: set[str] = set()

        while True:
            query: dict[str, str | int] = {"limit": limit}
            if cursor is None:
                query.update(params or {})
            else:
                query["cursor"] = cursor

            page = await self.get(path, query, customer=customer)
            yield page

            next_cursor = page.meta.get("next_cursor")
            if next_cursor is None:
                return

            if not isinstance(next_cursor, str) or not next_cursor:
                msg = f"GET {path} answered with a next_cursor that is not a string."
                raise SiteApiResponseError(msg, request_id=page.request_id)

            if next_cursor in seen:
                msg = f"GET {path} handed back a cursor it had already given."
                raise SiteApiResponseError(msg, request_id=page.request_id)

            seen.add(next_cursor)
            cursor = next_cursor


def _read(response: httpx.Response, where: str, request_id: str) -> SiteApiResponse:
    """Turns a response into the envelope's contents, or into the right error.

    Raises:
        SiteApiError: in one of the three flavours listed on the client.
    """
    status = response.status_code
    request_id = response.headers.get(REQUEST_ID_HEADER, request_id)

    if (
        status == HTTPStatus.TOO_MANY_REQUESTS
        or status >= HTTPStatus.INTERNAL_SERVER_ERROR
    ):
        code = _error_code(response)
        msg = f"The site API answered {where} with {status} ({code or 'no code'})."
        raise SiteApiUnavailableError(
            msg,
            status=status,
            code=code,
            request_id=request_id,
            retry_after=_retry_after(response),
        )

    if status >= HTTPStatus.BAD_REQUEST:
        code = _error_code(response)
        msg = f"The site API refused {where} with {status} ({code or 'no code'})."
        raise SiteApiRejectedError(
            msg,
            status=status,
            code=code,
            request_id=request_id,
            details=_error_details(response),
        )

    if status == HTTPStatus.NO_CONTENT:
        return SiteApiResponse(data=None, meta={}, request_id=request_id)

    if not HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES:
        msg = f"The site API answered {where} with {status}, which is not the contract."
        raise SiteApiResponseError(msg, status=status, request_id=request_id)

    return _envelope(response, where, request_id)


def _envelope(response: httpx.Response, where: str, request_id: str) -> SiteApiResponse:
    """The ``data`` and ``meta`` of a successful answer.

    Raises:
        SiteApiResponseError: the body is not JSON or not the envelope.
    """
    try:
        body = response.json()
    except ValueError as e:
        msg = f"The site API answered {where} with a body that is not JSON."
        raise SiteApiResponseError(
            msg,
            status=response.status_code,
            request_id=request_id,
        ) from e

    if not isinstance(body, dict) or "data" not in body:
        msg = f"The site API answered {where} without a 'data' envelope."
        raise SiteApiResponseError(
            msg, status=response.status_code, request_id=request_id
        )

    meta = body.get("meta") or {}
    if not isinstance(meta, dict):
        msg = f"The site API answered {where} with a 'meta' that is not an object."
        raise SiteApiResponseError(
            msg, status=response.status_code, request_id=request_id
        )

    return SiteApiResponse(data=body["data"], meta=meta, request_id=request_id)


def _error_body(response: httpx.Response) -> Mapping[str, object] | None:
    """The ``error`` object of a refusal, or ``None`` when the body has none."""
    try:
        body = response.json()
    except ValueError:
        return None

    if not isinstance(body, dict):
        return None

    error = body.get("error")
    return error if isinstance(error, dict) else None


def _error_details(response: httpx.Response) -> Mapping[str, object]:
    """``error.details`` of a refusal, empty when absent or not an object."""
    error = _error_body(response)
    details = None if error is None else error.get("details")
    return details if isinstance(details, dict) else {}


def _error_code(response: httpx.Response) -> str | None:
    """The stable ``error.code`` of a refusal, if the body carries one.

    Best effort by design: a 502 from the proxy in front of the site has an
    HTML body, and failing to read a code must not replace the status error
    with a parsing one.
    """
    error = _error_body(response)
    code = None if error is None else error.get("code")
    return code if isinstance(code, str) and code else None


def _retry_after(response: httpx.Response) -> float | None:
    """``Retry-After`` in seconds, the form the site sends it in.

    The header may also carry an HTTP date; the site does not use that form,
    and a date read against a clock that is not the site's would be a guess,
    so it is reported as absent rather than approximated.
    """
    value = response.headers.get("Retry-After")
    if not value:
        return None

    try:
        return max(float(value), 0.0)
    except ValueError:
        return None
