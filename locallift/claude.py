"""Claude synthesis constrained to LocalLift's deterministic evidence."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"
MAX_OUTPUT_TOKENS = 4096


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "executive_summary": {
            "type": "string",
            "description": "A concise executive summary of no more than two sentences.",
        },
        "priority_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "A short action title."},
                    "why": {"type": "string", "description": "Why this matters, in one concise sentence."},
                    "steps": {"type": "string", "description": "Implementation guidance in no more than two sentences."},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "why", "steps", "evidence_ids"],
                "additionalProperties": False,
            },
        },
        "metadata": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["title", "description"],
            "additionalProperties": False,
        },
        "human_checks": {
            "type": "array",
            "description": "At most four short checks that require data or judgment outside the supplied evidence.",
            "items": {"type": "string"},
        },
        "scale_note": {"type": "string", "description": "One concise sentence about scaling this workflow."},
    },
    "required": ["executive_summary", "priority_actions", "metadata", "human_checks", "scale_note"],
    "additionalProperties": False,
}


SYSTEM_PROMPT = """You are a senior local SEO specialist reviewing a medspa page or focused site crawl.
You receive machine-extracted facts and rule-based issue records, not Search Console, GBP, or rank data.

Non-negotiable rules:
- Use only supplied evidence. Never invent rankings, traffic, reviews, competitors, GBP details, or clinical claims.
- Prioritize at most three actions by organic impact, certainty, and implementation order.
- Keep the executive summary to two sentences, each action rationale to one sentence, each implementation to two sentences, each human check to one sentence, and the scale note to one sentence.
- Every priority action must cite one or more supplied issue IDs in evidence_ids.
- Distinguish facts from items that need a human, Search Console, GBP, crawl, or clinical review.
- Metadata may use only the supplied business name, city, service, and claims explicitly present in the facts. Do not add outcomes, credentials, technology, comfort, safety, experience, pricing, or superlatives that the evidence does not prove. A neutral consultation or booking CTA is allowed only when the visible page copy supports it.
- Keep the title at 60 characters or fewer and description at 155 or fewer.
- When naming business schema types, use only established types from this set: LocalBusiness, HealthAndBeautyBusiness, MedicalBusiness, or a type already present in the extracted facts. "MedicalSpa" is not an allowed type.
- For a site crawl, issue records may represent multiple affected URLs. Prioritize patterns by impact and affected-page count without claiming that every page needs identical local or schema signals.
- For a site crawl, the metadata proposal is for the supplied main site URL and must use the nested homepage facts.
- Do not recommend keyword stuffing, city doorway pages, review markup for self-serving reviews, or unverified medical promises.
- Write for an SEO manager who needs a concise action queue, not a generic audit essay."""


class ClaudeError(RuntimeError):
    """An AI request failed without invalidating the deterministic audit."""


def configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def _request_payload(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": "Create a grounded local SEO action plan from this evidence:\n" + json.dumps(context),
        }],
        "output_config": {
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
    }


def _validate(result: dict[str, Any], valid_issue_ids: set[str]) -> dict[str, Any]:
    actions = []
    for action in result.get("priority_actions", [])[:3]:
        evidence_ids = [item for item in action.get("evidence_ids", []) if item in valid_issue_ids]
        if evidence_ids:
            actions.append({
                "title": str(action.get("title", "")).strip(),
                "why": str(action.get("why", "")).strip(),
                "steps": str(action.get("steps", "")).strip(),
                "evidence_ids": evidence_ids,
            })

    metadata = result.get("metadata", {})
    title = str(metadata.get("title", "")).strip()
    description = str(metadata.get("description", "")).strip()
    return {
        "executive_summary": str(result.get("executive_summary", "")).strip(),
        "priority_actions": actions,
        "metadata": {
            "title": title,
            "description": description,
            "title_length": len(title),
            "description_length": len(description),
            "title_within_limit": len(title) <= 60,
            "description_within_limit": len(description) <= 155,
        },
        "human_checks": [str(item).strip() for item in result.get("human_checks", [])[:4] if str(item).strip()],
        "scale_note": str(result.get("scale_note", "")).strip(),
    }


def synthesize(site: dict[str, str], facts: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ClaudeError("Claude is not configured. Add ANTHROPIC_API_KEY to .env to enable live synthesis.")

    compact_facts = {
        key: value for key, value in facts.items()
        if key not in {"og_title", "og_description"}
    }
    compact_issues = []
    for issue in issues:
        record = {
            key: issue[key]
            for key in ("id", "severity", "category", "title", "finding", "evidence", "impact", "effort", "confidence")
        }
        if "affected_count" in issue:
            record["affected_count"] = issue["affected_count"]
            record["affected_pages"] = issue.get("affected_pages", [])[:5]
        compact_issues.append(record)
    payload = _request_payload({"site": site, "facts": compact_facts, "issues": compact_issues})
    request = Request(
        API_URL,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
        },
    )

    try:
        with urlopen(request, timeout=75) as response:
            data = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise ClaudeError(f"Claude returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ClaudeError(f"Claude could not be reached: {exc}") from exc

    if data.get("stop_reason") == "max_tokens":
        used = data.get("usage", {}).get("output_tokens", MAX_OUTPUT_TOKENS)
        raise ClaudeError(
            f"Claude reached the {used}-token output limit before completing the report. Retry synthesis."
        )
    if data.get("stop_reason") == "refusal":
        raise ClaudeError("Claude declined to synthesize this audit.")
    try:
        text = next(block["text"] for block in data["content"] if block.get("type") == "text")
        parsed = json.loads(text)
    except (KeyError, StopIteration, TypeError, json.JSONDecodeError) as exc:
        raise ClaudeError("Claude returned an unreadable structured response.") from exc

    validated = _validate(parsed, {issue["id"] for issue in issues})
    if not validated["priority_actions"] and issues:
        raise ClaudeError("Claude returned no action with a valid evidence reference.")
    return {
        "status": "complete",
        "mode": "live",
        "model": data.get("model", payload["model"]),
        "usage": data.get("usage", {}),
        "result": validated,
    }
