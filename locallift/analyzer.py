"""Fetch and extract auditable on-page SEO facts without third-party packages."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_PAGE_BYTES = 2_000_000
USER_AGENT = "LocalLift/1.0 (+local-seo-audit-demo)"


class AnalysisError(ValueError):
    """A user-facing fetch or page-analysis error."""


def _assert_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AnalysisError("Enter a complete public http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise AnalysisError("URLs containing credentials are not supported.")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except ValueError as exc:
        raise AnalysisError("The URL contains an invalid port.") from exc
    except socket.gaierror as exc:
        raise AnalysisError(f"Could not resolve {parsed.hostname}.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise AnalysisError("Only public internet URLs can be analyzed.")
    return parsed.geturl()


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        _assert_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_text(
    url: str,
    accepted_content_types: set[str],
    timeout: int = 15,
    max_bytes: int = MAX_PAGE_BYTES,
) -> tuple[str, dict[str, Any]]:
    """Fetch a public text resource with redirect and response-size guardrails."""
    safe_url = _assert_public_url(url)
    opener = build_opener(_SafeRedirectHandler())
    request = Request(
        safe_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if content_type not in accepted_content_types:
                raise AnalysisError(f"The URL returned unsupported content type {content_type}.")
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise AnalysisError(f"The resource is larger than the {max_bytes // 1_000_000} MB analysis limit.")
            charset = response.headers.get_content_charset() or "utf-8"
            html = body.decode(charset, errors="replace")
            return html, {
                "requested_url": safe_url,
                "final_url": response.geturl(),
                "status": getattr(response, "status", 200),
                "content_type": content_type,
                "bytes": len(body),
            }
    except AnalysisError:
        raise
    except HTTPError as exc:
        raise AnalysisError(f"The page returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AnalysisError(f"The page could not be fetched: {exc.reason if isinstance(exc, URLError) else exc}") from exc


def fetch_html(url: str, timeout: int = 15) -> tuple[str, dict[str, Any]]:
    """Fetch a public HTML page."""
    return fetch_text(url, {"text/html", "application/xhtml+xml"}, timeout=timeout)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _schema_types(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        schema_type = value.get("@type")
        if isinstance(schema_type, str):
            found.add(schema_type)
        elif isinstance(schema_type, list):
            found.update(item for item in schema_type if isinstance(item, str))
        for child in value.values():
            found.update(_schema_types(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_schema_types(child))
    return found


def _has_schema_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_has_schema_key(child, key) for child in value.values())
    if isinstance(value, list):
        return any(_has_schema_key(child, key) for child in value)
    return False


class SEOHTMLParser(HTMLParser):
    """Small purpose-built DOM event parser for the facts LocalLift needs."""

    SKIP_TEXT = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1s: list[str] = []
        self.body_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.images: list[dict[str, str | bool]] = []
        self.links: list[str] = []
        self.schema_blocks: list[Any] = []
        self.has_tel_link = False
        self._stack: list[str] = []
        self._h1_parts: list[str] | None = None
        self._jsonld_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {key.lower(): (value or "") for key, value in attrs}
        self._stack.append(tag)
        if tag == "meta":
            key = (attr.get("name") or attr.get("property") or "").lower()
            if key:
                self.meta[key] = _clean(attr.get("content", ""))
        elif tag == "link" and "canonical" in attr.get("rel", "").lower().split():
            self.canonical = attr.get("href", "").strip()
        elif tag == "img":
            self.images.append({
                "src": attr.get("src", ""),
                "alt": _clean(attr.get("alt", "")),
                "has_alt_attribute": "alt" in attr,
            })
        elif tag == "a":
            href = attr.get("href", "").strip()
            if href:
                self.links.append(href)
                self.has_tel_link = self.has_tel_link or href.lower().startswith("tel:")
        elif tag == "h1":
            self._h1_parts = []
        elif tag == "script" and attr.get("type", "").lower() == "application/ld+json":
            self._jsonld_parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self._stack:
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "h1" and self._h1_parts is not None:
            value = _clean(" ".join(self._h1_parts))
            if value:
                self.h1s.append(value)
            self._h1_parts = None
        elif tag == "script" and self._jsonld_parts is not None:
            raw = "".join(self._jsonld_parts).strip()
            try:
                if raw:
                    self.schema_blocks.append(json.loads(raw))
            except json.JSONDecodeError:
                self.schema_blocks.append({"_invalid_json_ld": True})
            self._jsonld_parts = None
        if tag in self._stack:
            reverse_index = self._stack[::-1].index(tag)
            del self._stack[len(self._stack) - reverse_index - 1 :]

    def handle_data(self, data: str) -> None:
        if self._jsonld_parts is not None:
            self._jsonld_parts.append(data)
            return
        if self._stack and self._stack[-1] == "title":
            self.title_parts.append(data)
        if self._h1_parts is not None:
            self._h1_parts.append(data)
        if not any(tag in self.SKIP_TEXT for tag in self._stack):
            value = _clean(data)
            if value:
                self.body_parts.append(value)


def extract_facts(
    html: str,
    page_url: str,
    business_name: str,
    city: str,
    service: str,
) -> dict[str, Any]:
    parser = SEOHTMLParser()
    parser.feed(html)

    title = _clean(" ".join(parser.title_parts))
    description = parser.meta.get("description", "")
    robots = parser.meta.get("robots", "")
    body_text = _clean(" ".join(parser.body_parts))
    body_lower = body_text.casefold()
    title_lower = title.casefold()
    h1_text = " ".join(parser.h1s).casefold()
    parsed_url = urlparse(page_url)

    internal_links = 0
    for href in parser.links:
        target = urlparse(urljoin(page_url, href))
        if target.scheme in {"http", "https"} and target.netloc == parsed_url.netloc:
            internal_links += 1

    schema_types: set[str] = set()
    for block in parser.schema_blocks:
        schema_types.update(_schema_types(block))

    image_gaps = [image for image in parser.images if not image["alt"]]
    words = re.findall(r"\b[\w'-]+\b", body_text)
    city_key = city.strip().casefold()
    service_key = service.strip().casefold()
    business_key = business_name.strip().casefold()

    local_schema_types = {
        "localbusiness", "medicalbusiness", "healthandbeautybusiness", "beautysalon", "daySpa".casefold()
    }
    normalized_schema = {item.casefold() for item in schema_types}

    return {
        "url": page_url,
        "title": title,
        "title_length": len(title),
        "meta_description": description,
        "meta_description_length": len(description),
        "h1s": parser.h1s,
        "h1_count": len(parser.h1s),
        "canonical": urljoin(page_url, parser.canonical) if parser.canonical else "",
        "robots": robots,
        "indexable": "noindex" not in robots.casefold(),
        "schema_types": sorted(schema_types),
        "has_local_business_schema": bool(normalized_schema & local_schema_types),
        "has_address_schema": any(_has_schema_key(block, "address") for block in parser.schema_blocks),
        "json_ld_blocks": len(parser.schema_blocks),
        "invalid_json_ld_blocks": sum(
            1 for block in parser.schema_blocks if isinstance(block, dict) and block.get("_invalid_json_ld")
        ),
        "images": len(parser.images),
        "images_without_alt": len(image_gaps),
        "word_count": len(words),
        "internal_links": internal_links,
        "has_phone_link": parser.has_tel_link,
        "city_in_title": bool(city_key and city_key in title_lower),
        "city_in_h1": bool(city_key and city_key in h1_text),
        "city_in_body": bool(city_key and city_key in body_lower),
        "service_in_title": bool(service_key and service_key in title_lower),
        "service_in_h1": bool(service_key and service_key in h1_text),
        "service_in_body": bool(service_key and service_key in body_lower),
        "brand_in_title": bool(business_key and business_key in title_lower),
        "og_title": parser.meta.get("og:title", ""),
        "og_description": parser.meta.get("og:description", ""),
    }
