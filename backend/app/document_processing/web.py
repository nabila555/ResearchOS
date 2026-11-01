"""Fetch a web page or PDF by URL, with SSRF protection and size limits.

Only public http(s) addresses are allowed: loopback, private, link-local, and
other non-global IPs are rejected for the initial URL and for every redirect.
"""

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app.document_processing.types import ProcessingError

MAX_REDIRECTS = 5
USER_AGENT = "ResearchOS/0.5 (local research assistant; +https://github.com/)"
HTML_TYPES = {"text/html", "application/xhtml+xml"}
TEXT_TYPES = {"text/plain", "text/markdown"}
PDF_TYPES = {"application/pdf", "application/x-pdf"}


class UnsafeUrlError(ProcessingError):
    pass


class FetchError(ProcessingError):
    pass


@dataclass
class FetchedResource:
    url: str
    content_type: str
    content: bytes

    @property
    def is_pdf(self) -> bool:
        return self.content_type in PDF_TYPES or self.content[:5] == b"%PDF-"

    @property
    def is_html(self) -> bool:
        return self.content_type in HTML_TYPES

    def text(self, charset: str | None = None) -> str:
        try:
            return self.content.decode(charset or "utf-8")
        except (UnicodeDecodeError, LookupError):
            return self.content.decode("cp1252", errors="replace")


Resolver = Callable[[str], list[str]]


def resolve_host(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve host “{host}”.") from exc
    return [str(info[4][0]) for info in infos]


def validate_public_url(url: str, resolver: Resolver = resolve_host) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only http:// and https:// URLs can be imported.")
    if not parts.hostname:
        raise UnsafeUrlError("The URL has no host name.")
    if parts.username or parts.password:
        raise UnsafeUrlError("URLs with embedded credentials are not allowed.")
    addresses = resolver(parts.hostname)
    if not addresses:
        raise FetchError(f"Could not resolve host “{parts.hostname}”.")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeUrlError(
                "Importing from local or private network addresses is not allowed."
            )
    return parts.geturl()


def fetch_url(
    url: str,
    *,
    max_bytes: int,
    timeout: float = 20.0,
    transport: httpx.BaseTransport | None = None,
    resolver: Resolver = resolve_host,
) -> FetchedResource:
    current = url
    with httpx.Client(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.5"},
        transport=transport,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            current = validate_public_url(current, resolver)
            try:
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("The server sent a redirect without a location.")
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 400:
                        raise FetchError(f"The server responded with HTTP {response.status_code}.")
                    content_type = (
                        response.headers.get("content-type", "").split(";")[0].strip().lower()
                    )
                    declared = int(response.headers.get("content-length") or 0)
                    if declared > max_bytes:
                        raise FetchError("The resource is larger than the upload size limit.")
                    body = bytearray()
                    for block in response.iter_bytes():
                        body.extend(block)
                        if len(body) > max_bytes:
                            raise FetchError("The resource is larger than the upload size limit.")
                    resource = FetchedResource(str(response.url), content_type, bytes(body))
            except httpx.TimeoutException as exc:
                raise FetchError("The request timed out.") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"Could not download the URL ({type(exc).__name__}).") from exc
            if not (resource.is_pdf or resource.is_html or content_type in TEXT_TYPES):
                raise FetchError(
                    f"Unsupported content type “{content_type or 'unknown'}”. "
                    "Web pages, plain text, and PDFs can be imported."
                )
            return resource
    raise FetchError("Too many redirects.")
