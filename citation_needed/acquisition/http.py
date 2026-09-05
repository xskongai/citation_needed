from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AcquisitionNetworkError(RuntimeError):
    pass


class ContentTooLargeError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    url: str
    headers: dict[str, str]
    body: bytes

    def json(self) -> object:
        return json.loads(self.body.decode("utf-8"))


class HttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 20.0,
        max_bytes: int = 50_000_000,
    ) -> HttpResponse: ...


class UrllibHttpClient:
    """Small stdlib HTTP client so acquisition has no extra runtime dependency."""

    def __init__(self, user_agent: str = "CitationNeeded/0.11 (+source-acquisition)") -> None:
        self.user_agent = user_agent

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 20.0,
        max_bytes: int = 50_000_000,
    ) -> HttpResponse:
        merged = {"User-Agent": self.user_agent, "Accept": "*/*"}
        if headers:
            merged.update(dict(headers))
        req = Request(url, headers=merged, method="GET")
        try:
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ContentTooLargeError(f"Response exceeded max_bytes={max_bytes}.")
                return HttpResponse(
                    status_code=getattr(resp, "status", 200),
                    url=resp.geturl(),
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    body=body,
                )
        except HTTPError as exc:
            try:
                body = exc.read(min(max_bytes, 1_000_000))
            except Exception:
                body = b""
            return HttpResponse(
                status_code=exc.code,
                url=getattr(exc, "url", url),
                headers={k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])},
                body=body,
            )
        except (URLError, TimeoutError, OSError) as exc:
            raise AcquisitionNetworkError(str(exc)) from exc
