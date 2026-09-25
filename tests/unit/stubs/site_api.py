"""Stand-ins for the site tkgoldy.ru at the HTTP level.

Transports rather than a stub of ``SiteApiClient``: the client's whole job is
the translation from HTTP to our errors and our envelope, so the tests have to
reach it with real ``httpx`` requests and real ``httpx`` responses. No socket
is opened — httpx hands the request to the transport in process.
"""

from typing import final, override

import httpx


@final
class ScriptedTransport(httpx.AsyncBaseTransport):
    """Answers each request with the next scripted response, or raises it.

    For the client's own tests, where what matters is how one answer is read —
    a 429, a body that is not JSON, a connection that never opened.
    """

    def __init__(self, *answers: httpx.Response | Exception) -> None:
        self._answers = list(answers)
        self.requests: list[httpx.Request] = []

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self._answers.pop(0)

        if isinstance(answer, Exception):
            raise answer

        return answer


@final
class FakeSiteCatalog(httpx.AsyncBaseTransport):
    """The site's three catalog endpoints, served from lists a test fills in.

    Items are served page by page with the page's index as the cursor, the way
    the site hands out an opaque string. ``failures`` replaces the answer for
    one endpoint — keyed by the last path segment, and for items by page
    index as well — so a test can make the site refuse the sections or time
    out on the second page.
    """

    def __init__(self) -> None:
        self.sections: list[object] = []
        self.price_types: list[object] = []
        self.item_pages: list[list[object]] = []
        self.failures: dict[str, httpx.Response | Exception] = {}
        self.requests: list[httpx.Request] = []

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        endpoint = request.url.path.rsplit("/", 1)[-1]

        if endpoint == "items":
            page = int(request.url.params.get("cursor", "0"))
            return self._answer(f"items:{page}", self._items(page))

        if endpoint == "sections":
            return self._answer(endpoint, envelope(self.sections))

        if endpoint == "price-types":
            return self._answer(endpoint, envelope(self.price_types))

        return httpx.Response(404, json={"error": {"code": "not_found"}})

    def _items(self, page: int) -> httpx.Response:
        rows = self.item_pages[page] if page < len(self.item_pages) else []
        next_cursor = str(page + 1) if page + 1 < len(self.item_pages) else None
        return envelope(rows, next_cursor=next_cursor)

    def _answer(self, key: str, default: httpx.Response) -> httpx.Response:
        failure = self.failures.get(key)
        if failure is None:
            return default
        if isinstance(failure, Exception):
            raise failure
        return failure


def envelope(data: object, **meta: object) -> httpx.Response:
    """A 200 in the site's envelope, with ``meta`` as given."""
    return httpx.Response(200, json={"data": data, "meta": {"request_id": "r", **meta}})
