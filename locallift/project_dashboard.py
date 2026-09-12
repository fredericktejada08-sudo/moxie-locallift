"""Build a compact, evidence-linked view of a project's latest audit."""

from __future__ import annotations

from typing import Any


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _severity(issues: list[dict[str, Any]]) -> str:
    values = [_text(issue.get("severity")).lower() for issue in issues]
    values = [value for value in values if value in SEVERITY_RANK]
    return min(values, key=SEVERITY_RANK.get) if values else "low"


def _affected_pages(issues: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    pages: dict[str, dict[str, Any]] = {}
    reported_count = 0
    for issue in issues:
        reported_count = max(reported_count, int(issue.get("affected_count", 0) or 0))
        for page in issue.get("affected_pages", []):
            if not isinstance(page, dict):
                continue
            url = _text(page.get("url"))
            if not url or url in pages:
                continue
            pages[url] = {
                "url": url,
                "title": _text(page.get("page_title")) or url,
                "page_type": _text(page.get("page_type")) or "page",
                "score": int(page.get("page_score", 0) or 0),
            }
    count = max(reported_count, len(pages))
    return count, list(pages.values())[:5]


def _action(
    rank: int,
    title: Any,
    why: Any,
    steps: Any,
    evidence_ids: list[str],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    affected_count, affected_pages = _affected_pages(issues)
    efforts = {_text(issue.get("effort")) for issue in issues if _text(issue.get("effort"))}
    return {
        "rank": rank,
        "title": _text(title) or "Review audit finding",
        "why": _text(why),
        "steps": _text(steps),
        "severity": _severity(issues),
        "effort": next(iter(efforts)) if len(efforts) == 1 else "",
        "evidence_ids": evidence_ids,
        "affected_count": affected_count,
        "affected_pages": affected_pages,
    }


def build_project_dashboard(project: dict[str, Any], audit: dict[str, Any] | None) -> dict[str, Any]:
    """Distill the latest snapshot into decisions without returning the full crawl."""
    if not audit:
        return {
            "audit": None,
            "summary": "Run an audit and save it to this project to generate recommendations.",
            "recommendation_source": "none",
            "actions": [],
            "human_checks": [],
            "scale_note": "",
        }

    issue_list = [issue for issue in audit.get("issues", []) if isinstance(issue, dict)]
    issues_by_id = {_text(issue.get("id")): issue for issue in issue_list}
    ai = audit.get("ai", {}) if isinstance(audit.get("ai"), dict) else {}
    ai_result = ai.get("result", {}) if isinstance(ai.get("result"), dict) else {}
    ai_actions = ai_result.get("priority_actions", [])
    actions: list[dict[str, Any]] = []

    if ai.get("status") == "complete" and isinstance(ai_actions, list):
        for item in ai_actions:
            if not isinstance(item, dict):
                continue
            evidence_ids = [
                _text(value) for value in item.get("evidence_ids", [])
                if _text(value) in issues_by_id
            ]
            matched = [issues_by_id[value] for value in evidence_ids]
            actions.append(_action(
                len(actions) + 1,
                item.get("title"),
                item.get("why"),
                item.get("steps"),
                evidence_ids,
                matched,
            ))

    recommendation_source = "claude" if actions else "audit"
    if not actions:
        for issue in issue_list:
            issue_id = _text(issue.get("id"))
            actions.append(_action(
                len(actions) + 1,
                issue.get("title"),
                issue.get("impact") or issue.get("finding"),
                issue.get("recommendation"),
                [issue_id] if issue_id else [],
                [issue],
            ))

    audit_summary = next(
        (item for item in project.get("audits", []) if item.get("id") == audit.get("id")),
        {},
    )
    summary = _text(ai_result.get("executive_summary"))
    if not summary:
        summary = (
            f"The latest audit found {len(issue_list)} prioritized issue "
            f"{'group' if len(issue_list) == 1 else 'groups'} across "
            f"{int(audit.get('facts', {}).get('pages_analyzed', 1) or 1)} analyzed pages."
            if issue_list else "The latest audit has no open recommendations."
        )

    human_checks = ai_result.get("human_checks", [])
    return {
        "audit": {
            "id": _text(audit.get("id")),
            "audit_type": _text(audit.get("audit_type")) or "page",
            "business_name": _text(audit.get("site", {}).get("business_name")),
            "url": _text(audit.get("site", {}).get("url")),
            "score": int(audit.get("score", 0) or 0),
            "issue_count": len(issue_list),
            "page_count": int(audit.get("facts", {}).get("pages_analyzed", 1) or 1),
            "created_at": _text(audit_summary.get("created_at")),
        },
        "summary": summary,
        "recommendation_source": recommendation_source,
        "actions": actions,
        "human_checks": [_text(item) for item in human_checks if _text(item)]
        if isinstance(human_checks, list) else [],
        "scale_note": _text(ai_result.get("scale_note")),
    }
