"""Deterministic SEO checks that keep AI prioritization tied to evidence."""

from __future__ import annotations

from typing import Any


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _issue(
    issue_id: str,
    category: str,
    severity: str,
    title: str,
    finding: str,
    evidence: str,
    impact: str,
    recommendation: str,
    weight: int,
    effort: str = "Low",
    confidence: str = "High",
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "category": category,
        "severity": severity,
        "title": title,
        "finding": finding,
        "evidence": evidence,
        "impact": impact,
        "recommendation": recommendation,
        "effort": effort,
        "confidence": confidence,
        "weight": weight,
    }


def evaluate(
    facts: dict[str, Any],
    city: str,
    service: str,
    page_type: str = "single",
) -> tuple[int, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    needs_local_signals = page_type in {"single", "homepage", "service", "location"}
    needs_business_schema = page_type in {"single", "homepage", "location"}
    needs_depth = page_type in {"single", "homepage", "service", "article", "about", "general"}
    needs_phone = page_type in {"single", "homepage", "service", "location", "contact"}
    needs_brand_title = page_type != "article"

    if not facts["indexable"]:
        issues.append(_issue(
            "indexability.noindex", "Indexability", "critical", "Page is marked noindex",
            "The robots meta directive prevents this page from appearing in organic search.",
            f'robots meta: "{facts["robots"]}"',
            "A commercially relevant page cannot rank while noindex is present.",
            "Confirm the directive is unintentional, remove noindex, then request reindexing in GSC.",
            30,
        ))

    title = facts["title"]
    if not title:
        issues.append(_issue(
            "metadata.title_missing", "Metadata", "critical", "Title tag is missing",
            "No title element with usable text was extracted.", "title length: 0",
            "Search engines lose a primary relevance and click-through signal.",
            "Write a unique title that combines the service, city, and brand.", 20,
        ))
    else:
        if facts["title_length"] < 30 or facts["title_length"] > 60:
            issues.append(_issue(
                "metadata.title_length", "Metadata", "medium", "Title length needs review",
                f'The title is {facts["title_length"]} characters.', f'title: "{title}"',
                "Titles outside the working range may under-communicate relevance or truncate in results.",
                "Rewrite around 45-60 characters while preserving the primary query and brand.", 5,
            ))
        if city and needs_local_signals and not facts["city_in_title"]:
            issues.append(_issue(
                "local.city_title", "Local relevance", "high", "City is absent from the title",
                f'The target city "{city}" was not found in the title.', f'title: "{title}"',
                "The page sends a weaker location signal for local-intent searches.",
                f'Add "{city}" naturally to the title without keyword stuffing.', 10,
            ))
        if service and page_type in {"single", "service"} and not facts["service_in_title"]:
            issues.append(_issue(
                "metadata.service_title", "Metadata", "high", "Primary service is absent from the title",
                f'The target service "{service}" was not found in the title.', f'title: "{title}"',
                "The title does not clearly align the page with its intended commercial query.",
                f'Lead with "{service}" and retain the city and brand.', 8,
            ))
        if needs_brand_title and not facts["brand_in_title"]:
            issues.append(_issue(
                "metadata.brand_title", "Metadata", "low", "Brand is absent from the title",
                "The supplied business name was not found in the title.", f'title: "{title}"',
                "Brand recognition and entity consistency are weaker in the search result.",
                "Include the business name, usually at the end of the title.", 3,
            ))

    description = facts["meta_description"]
    if not description:
        issues.append(_issue(
            "metadata.description_missing", "Metadata", "high", "Meta description is missing",
            "No meta description was extracted.", "description length: 0",
            "Search engines must generate their own snippet, reducing message and CTA control.",
            "Write a unique 120-155 character description with service, location, a supported detail, and CTA.", 10,
        ))
    elif facts["meta_description_length"] < 90 or facts["meta_description_length"] > 160:
        issues.append(_issue(
            "metadata.description_length", "Metadata", "medium", "Meta description length needs review",
            f'The description is {facts["meta_description_length"]} characters.',
            f'description: "{description}"',
            "An overly short or long snippet gives less control over search-result messaging.",
            "Rewrite to roughly 120-155 characters and keep the value proposition specific.", 4,
        ))

    if facts["h1_count"] == 0:
        issues.append(_issue(
            "content.h1_missing", "Content", "high", "H1 is missing",
            "No H1 heading was extracted.", "H1 count: 0",
            "The main page topic is less explicit to users and crawlers.",
            f'Add one descriptive H1 centered on "{service}" and the local intent.'
            if service else "Add one descriptive H1 that states the page's primary topic.", 12,
        ))
    elif facts["h1_count"] > 1:
        issues.append(_issue(
            "content.h1_multiple", "Content", "medium", "Multiple H1 headings need review",
            f'{facts["h1_count"]} H1 headings were extracted.', f'H1s: {facts["h1s"]}',
            "Competing primary headings can blur the page hierarchy.",
            "Keep one primary H1 and demote secondary headings where they are not true page titles.", 5,
        ))

    if not facts["canonical"]:
        issues.append(_issue(
            "technical.canonical_missing", "Technical", "medium", "Canonical tag is missing",
            "No canonical link was extracted.", "canonical: missing",
            "Duplicate URL variants have no explicit preferred version.",
            "Add a self-referencing absolute canonical after confirming the preferred URL.", 5,
        ))

    if needs_business_schema and not facts["has_local_business_schema"]:
        issues.append(_issue(
            "schema.local_business_missing", "Structured data", "high", "Local business schema is missing",
            "No LocalBusiness or compatible subtype was found in JSON-LD.",
            f'schema types: {facts["schema_types"] or "none"}',
            "Search engines receive less explicit business and location context.",
            "Add valid JSON-LD using the most specific LocalBusiness subtype and consistent NAP data.", 9,
            effort="Medium",
        ))
    elif needs_business_schema and not facts["has_address_schema"]:
        issues.append(_issue(
            "schema.address_missing", "Structured data", "medium", "Structured address is missing",
            "A local business schema type exists, but no address property was found.",
            f'schema types: {facts["schema_types"]}',
            "The markup does not fully connect the entity to its physical location.",
            "Add a PostalAddress that exactly matches the website and Google Business Profile.", 5,
        ))

    if facts["invalid_json_ld_blocks"]:
        issues.append(_issue(
            "schema.invalid_json", "Structured data", "high", "JSON-LD contains invalid JSON",
            f'{facts["invalid_json_ld_blocks"]} JSON-LD block(s) could not be parsed.',
            f'JSON-LD blocks: {facts["json_ld_blocks"]}',
            "Invalid structured data may be ignored entirely.",
            "Validate and repair the affected block with Schema.org and Rich Results testing tools.", 9,
        ))

    if facts["images_without_alt"]:
        ratio = facts["images_without_alt"] / max(1, facts["images"])
        severity = "medium" if ratio >= 0.5 else "low"
        issues.append(_issue(
            "accessibility.alt_review", "Images", severity, "Image alt text needs human review",
            f'{facts["images_without_alt"]} of {facts["images"]} images have an empty or missing alt value.',
            f'images without usable alt: {facts["images_without_alt"]}/{facts["images"]}',
            "Meaningful images may lose accessibility context and image-search relevance.",
            "Describe informative images; keep genuinely decorative images empty.", 5 if ratio >= 0.5 else 2,
            confidence="Medium",
        ))

    if needs_depth and facts["word_count"] < 180:
        issues.append(_issue(
            "content.thin_review", "Content", "medium", "Page depth needs human review",
            f'Only {facts["word_count"]} visible words were extracted.', f'visible word count: {facts["word_count"]}',
            "The page may not answer enough service, suitability, process, recovery, or pricing questions.",
            "Compare against search intent before expanding; add only useful, medically reviewed information.", 6,
            effort="Medium", confidence="Medium",
        ))

    if city and needs_local_signals and not facts["city_in_body"]:
        issues.append(_issue(
            "local.city_body", "Local relevance", "medium", "Target city is absent from page copy",
            f'The target city "{city}" was not found in visible body text.', "city match in body: false",
            "The page provides limited contextual support for its local search target.",
            "Add location context where it helps patients, such as the intro, directions, or service area copy.", 5,
        ))

    if needs_phone and not facts["has_phone_link"]:
        issues.append(_issue(
            "local.phone_link", "Local relevance", "low", "No clickable phone link was found",
            "The page contains no tel: link.", "tel links: 0",
            "Mobile visitors have a less direct conversion path and NAP is harder to verify automatically.",
            "Expose the primary local phone number as a clickable link in the header or contact area.", 2,
            confidence="Medium",
        ))

    issues.sort(key=lambda item: (SEVERITY_RANK[item["severity"]], -item["weight"], item["id"]))
    score = max(0, 100 - min(100, sum(item["weight"] for item in issues)))
    return score, issues
