"""Focused same-site crawler for portfolio-scale local SEO triage."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from xml.etree import ElementTree

from locallift.analyzer import AnalysisError, SEOHTMLParser, extract_facts, fetch_html, fetch_text
from locallift.claude import ClaudeError, synthesize
from locallift.rules import SEVERITY_RANK, evaluate


SITEMAP_TYPES = {
    "application/xml",
    "application/rss+xml",
    "application/octet-stream",
    "text/html",
    "text/plain",
    "text/xml",
}
ROBOTS_TYPES = {"text/plain", "text/html", "application/octet-stream"}
STATIC_EXTENSIONS = {
    ".7z", ".avi", ".css", ".csv", ".doc", ".docx", ".eot", ".gif", ".gz", ".ico",
    ".jpeg", ".jpg", ".js", ".json", ".map", ".mov", ".mp3", ".mp4", ".pdf", ".png",
    ".ppt", ".pptx", ".rar", ".svg", ".tar", ".tif", ".tiff", ".ttf", ".txt", ".wav",
    ".webm", ".webp", ".woff", ".woff2", ".xls", ".xlsx", ".xml", ".zip",
}
EXCLUDED_SEGMENTS = {
    "account", "author", "cart", "category", "checkout", "feed", "login", "logout", "my-account",
    "privacy", "privacy-policy", "search", "tag", "terms", "terms-and-conditions", "thank-you",
    "wp-admin", "wp-json", "wp-login.php",
}
SERVICE_TOKENS = {
    "aesthetic", "aesthetics", "botox", "body", "chemical", "contouring", "coolsculpting", "dermal",
    "dysport", "facial", "facials", "filler", "fillers", "hair", "hydrafacial", "injectable",
    "injectables", "iv", "laser", "microneedling", "peel", "peels", "prf", "prp", "rejuvenation",
    "sculpting", "skin", "tattoo", "treatment", "treatments", "ultherapy", "wellness",
}
LOCATION_TOKENS = {"areas", "directions", "location", "locations", "visit"}
ABOUT_TOKENS = {"about", "doctor", "meet", "our-story", "provider", "providers", "team"}
CONTACT_TOKENS = {"book", "booking", "contact", "consultation", "schedule"}
ARTICLE_TOKENS = {"article", "articles", "blog", "insights", "news", "resources"}


def _host_key(url: str) -> str:
    host = (urlparse(url).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _normalize_candidate(
    base_url: str,
    href: str,
    site_host: str,
    require_applicable_page: bool = True,
) -> str | None:
    absolute, _ = urldefrag(urljoin(base_url, href.strip()))
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or _host_key(absolute) != site_host:
        return None
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    if require_applicable_page and not is_applicable_url(normalized):
        return None
    return normalized


def is_applicable_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.casefold()
    if any(path.endswith(extension) for extension in STATIC_EXTENSIONS):
        return False
    segments = {segment for segment in path.split("/") if segment}
    if segments & EXCLUDED_SEGMENTS:
        return False
    if re.search(r"/(page/\d+|\d{4}/\d{1,2}/?$)", path):
        return False
    return True


def classify_page(url: str) -> str:
    path = urlparse(url).path.strip("/").casefold()
    if not path:
        return "homepage"
    tokens = set(re.split(r"[/_-]+", path))
    if tokens & ARTICLE_TOKENS:
        return "article"
    if tokens & LOCATION_TOKENS:
        return "location"
    if tokens & CONTACT_TOKENS:
        return "contact"
    if tokens & ABOUT_TOKENS:
        return "about"
    if tokens & SERVICE_TOKENS:
        return "service"
    return "general"


def topic_from_url(url: str) -> str:
    segments = [segment for segment in urlparse(url).path.split("/") if segment]
    if not segments:
        return ""
    value = re.sub(r"[-_]+", " ", segments[-1]).strip()
    return " ".join(word.capitalize() for word in value.split())


def _extract_links(html: str, page_url: str, site_host: str) -> list[str]:
    parser = SEOHTMLParser()
    parser.feed(html)
    found = []
    seen = set()
    for href in parser.links:
        candidate = _normalize_candidate(page_url, href, site_host)
        if candidate and candidate not in seen:
            seen.add(candidate)
            found.append(candidate)
    return found


def _xml_locs(xml_text: str) -> tuple[str, list[str]]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise AnalysisError("A discovered sitemap contains invalid XML.") from exc
    root_name = root.tag.rsplit("}", 1)[-1].casefold()
    locs = [
        (element.text or "").strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1].casefold() == "loc" and (element.text or "").strip()
    ]
    return root_name, locs


def _discover_sitemaps(origin: str) -> list[str]:
    candidates = []
    try:
        robots, _ = fetch_text(urljoin(origin, "/robots.txt"), ROBOTS_TYPES, timeout=8, max_bytes=500_000)
        for line in robots.splitlines():
            if line.casefold().startswith("sitemap:"):
                candidate = line.split(":", 1)[1].strip()
                if candidate:
                    candidates.append(candidate)
    except AnalysisError:
        pass
    candidates.append(urljoin(origin, "/sitemap.xml"))
    return list(dict.fromkeys(candidates))


def _discovery_priority(url: str) -> tuple[int, int, int, str]:
    order = {"homepage": 0, "service": 1, "location": 2, "about": 3, "contact": 4, "general": 5, "article": 6}
    page_type = classify_page(url)
    path = urlparse(url).path.strip("/")
    return order[page_type], path.count("/"), len(path), url


def discover_urls(root_url: str, max_pages: int) -> tuple[list[str], dict[str, Any], str, str]:
    """Discover and prioritize applicable same-site URLs from sitemap + homepage links."""
    homepage_html, homepage_fetch = fetch_html(root_url)
    homepage_url = homepage_fetch["final_url"]
    parsed = urlparse(homepage_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    site_host = _host_key(homepage_url)
    candidates = {homepage_url}
    sitemap_pages = set()
    sitemap_queue = _discover_sitemaps(origin)
    visited_sitemaps = set()
    sitemap_errors: list[str] = []

    while sitemap_queue and len(visited_sitemaps) < 10 and len(sitemap_pages) < max_pages * 8:
        sitemap_url = sitemap_queue.pop(0)
        normalized_map = _normalize_candidate(
            origin, sitemap_url, site_host, require_applicable_page=False
        )
        if not normalized_map or normalized_map in visited_sitemaps:
            continue
        visited_sitemaps.add(normalized_map)
        try:
            xml_text, _ = fetch_text(normalized_map, SITEMAP_TYPES, timeout=10, max_bytes=4_000_000)
            root_name, locs = _xml_locs(xml_text)
        except AnalysisError as exc:
            sitemap_errors.append(f"{normalized_map}: {exc}")
            continue
        if root_name == "sitemapindex":
            sitemap_queue.extend(locs)
            continue
        for loc in locs:
            candidate = _normalize_candidate(homepage_url, loc, site_host)
            if candidate:
                sitemap_pages.add(candidate)

    candidates.update(sitemap_pages)
    internal_pages = set(_extract_links(homepage_html, homepage_url, site_host))
    candidates.update(internal_pages)
    ordered = sorted(candidates, key=_discovery_priority)
    if homepage_url in ordered:
        ordered.remove(homepage_url)
    ordered.insert(0, homepage_url)
    selected = ordered[:max_pages]
    discovery = {
        "method": "sitemap + homepage links" if sitemap_pages else "homepage links",
        "sitemaps_checked": len(visited_sitemaps),
        "sitemap_errors": sitemap_errors[:3],
        "eligible_urls": len(ordered),
        "sitemap_urls": len(sitemap_pages),
        "homepage_links": len(internal_pages),
        "limit_reached": len(ordered) > max_pages,
    }
    return selected, discovery, homepage_html, homepage_url


def _audit_page(
    url: str,
    business_name: str,
    city: str,
    priority_service: str,
    prefetched: tuple[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    html, fetch = prefetched if prefetched else fetch_html(url)
    if _host_key(fetch["final_url"]) != _host_key(url):
        raise AnalysisError("A crawled page redirected outside the audited site.")
    page_type = classify_page(fetch["final_url"])
    derived_topic = topic_from_url(fetch["final_url"]) if page_type == "service" else ""
    if priority_service and all(
        token in urlparse(fetch["final_url"]).path.casefold()
        for token in re.findall(r"[a-z0-9]+", priority_service.casefold())
    ):
        derived_topic = priority_service
        page_type = "service"
    facts = extract_facts(html, fetch["final_url"], business_name, city, derived_topic)
    score, issues = evaluate(facts, city, derived_topic, page_type=page_type)
    return {
        "url": fetch["final_url"],
        "page_type": page_type,
        "target_topic": derived_topic,
        "score": score,
        "fetch": fetch,
        "facts": facts,
        "issues": issues,
    }


def _aggregate_issues(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for page in pages:
        for issue in page["issues"]:
            groups.setdefault(issue["id"], []).append((page, issue))

    aggregated = []
    for issue_id, records in groups.items():
        records.sort(key=lambda record: (SEVERITY_RANK[record[1]["severity"]], record[0]["score"]))
        base = records[0][1]
        affected = [{
            "url": page["url"],
            "page_type": page["page_type"],
            "page_title": page["facts"]["title"],
            "page_score": page["score"],
            "evidence": issue["evidence"],
        } for page, issue in records]
        count = len(affected)
        aggregated.append({
            **base,
            "finding": f"{count} page{'s' if count != 1 else ''} affected. {base['finding']}",
            "evidence": f"{count} page{'s' if count != 1 else ''} affected. Example: {base['evidence']}",
            "weight": base["weight"] * min(count, 4),
            "affected_pages": affected,
            "affected_count": count,
        })
    aggregated.sort(key=lambda item: (SEVERITY_RANK[item["severity"]], -item["weight"], item["id"]))
    return aggregated


def crawl_site(site: dict[str, Any], use_ai: bool = False) -> dict[str, Any]:
    business_name = str(site.get("business_name", "")).strip()
    city = str(site.get("city", "")).strip()
    priority_service = str(site.get("service", "")).strip()
    root_url = str(site.get("url", "")).strip()
    try:
        max_pages = int(site.get("max_pages", 25))
    except (TypeError, ValueError) as exc:
        raise AnalysisError("Crawl limit must be a number.") from exc
    if not all((business_name, city, root_url)):
        raise AnalysisError("Business name, city, and main site URL are required.")
    if any(len(value) > 250 for value in (business_name, city, priority_service, root_url)):
        raise AnalysisError("One or more fields exceed the 250-character limit.")
    if not 5 <= max_pages <= 50:
        raise AnalysisError("Crawl limit must be between 5 and 50 pages.")

    urls, discovery, homepage_html, homepage_url = discover_urls(root_url, max_pages)
    pages: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    homepage_meta = {
        "requested_url": root_url,
        "final_url": homepage_url,
        "status": 200,
        "content_type": "text/html",
        "bytes": len(homepage_html.encode("utf-8")),
    }
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for url in urls:
            prefetched = (homepage_html, homepage_meta) if url == homepage_url else None
            futures[executor.submit(
                _audit_page, url, business_name, city, priority_service, prefetched
            )] = url
        for future in as_completed(futures):
            try:
                pages.append(future.result())
            except AnalysisError as exc:
                errors.append({"url": futures[future], "error": str(exc)})

    if not pages:
        raise AnalysisError("No eligible HTML pages could be analyzed.")
    pages.sort(key=lambda page: (_discovery_priority(page["url"]), page["url"]))
    issues = _aggregate_issues(pages)
    page_types = Counter(page["page_type"] for page in pages)
    score = round(sum(page["score"] for page in pages) / len(pages))
    homepage = next((page for page in pages if page["page_type"] == "homepage"), pages[0])
    facts = {
        "pages_discovered": discovery["eligible_urls"],
        "pages_analyzed": len(pages),
        "pages_failed": len(errors),
        "indexable_pages": sum(1 for page in pages if page["facts"]["indexable"]),
        "noindex_pages": sum(1 for page in pages if not page["facts"]["indexable"]),
        "missing_titles": sum(1 for page in pages if not page["facts"]["title"]),
        "missing_descriptions": sum(1 for page in pages if not page["facts"]["meta_description"]),
        "missing_canonicals": sum(1 for page in pages if not page["facts"]["canonical"]),
        "images": sum(page["facts"]["images"] for page in pages),
        "images_without_alt": sum(page["facts"]["images_without_alt"] for page in pages),
        "page_types": dict(sorted(page_types.items())),
        "discovery": discovery,
        "homepage": homepage["facts"],
    }
    site_context = {
        "audit_kind": "site",
        "business_name": business_name,
        "city": city,
        "service": priority_service,
        "url": homepage_url,
    }
    result: dict[str, Any] = {
        "audit_type": "site",
        "id": "site-" + hashlib.sha1(homepage_url.encode("utf-8")).hexdigest()[:10],
        "site": site_context,
        "source": {
            "mode": "live_crawl",
            "requested_url": root_url,
            "final_url": homepage_url,
            "status": homepage_meta["status"],
            "content_type": "text/html",
            "bytes": sum(page["fetch"]["bytes"] for page in pages),
            "errors": errors,
        },
        "score": score,
        "issues": issues,
        "facts": facts,
        "pages": pages,
        "ai": {"status": "not_requested", "mode": "none"},
    }
    if use_ai:
        try:
            result["ai"] = synthesize(site_context, facts, issues[:30])
        except ClaudeError as exc:
            result["ai"] = {"status": "unavailable", "mode": "live", "error": str(exc)}
    return result
