"""Persistent LocalLift projects and private Google connection records."""

from __future__ import annotations

import json
import os
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from locallift.analyzer import AnalysisError


PROJECT_ID_PATTERN = re.compile(r"proj-[a-f0-9]{12}")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, label: str, required: bool = True, limit: int = 250) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise AnalysisError(f"{label} is required.")
    if len(text) > limit:
        raise AnalysisError(f"{label} exceeds the {limit}-character limit.")
    return text


class ProjectStore:
    """Thread-safe JSON persistence with audit snapshots separated by project."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.projects_file = data_dir / "projects.json"
        self.tokens_file = data_dir / "google_tokens.json"
        self.audits_dir = data_dir / "audits"
        self._lock = threading.RLock()

    def _prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audits_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.data_dir, 0o700)
        except OSError:
            pass

    @staticmethod
    def _read(path: Path, default: Any) -> Any:
        if not path.exists():
            return deepcopy(default)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AnalysisError(f"Local project data could not be read: {path.name}.") from exc

    def _write(self, path: Path, value: Any, private: bool = False) -> None:
        self._prepare()
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")
        if private:
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
        os.replace(temporary, path)

    @staticmethod
    def valid_project_id(project_id: str) -> bool:
        return bool(PROJECT_ID_PATTERN.fullmatch(project_id))

    def _records(self) -> list[dict[str, Any]]:
        records = self._read(self.projects_file, [])
        if not isinstance(records, list):
            raise AnalysisError("Local project data has an invalid format.")
        return records

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            records = self._records()
            records.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
            return deepcopy(records)

    def get_project(self, project_id: str) -> dict[str, Any]:
        if not self.valid_project_id(project_id):
            raise AnalysisError("Unknown project.")
        with self._lock:
            project = next((item for item in self._records() if item.get("id") == project_id), None)
            if not project:
                raise AnalysisError("Unknown project.")
            return deepcopy(project)

    def create_project(self, values: dict[str, Any]) -> dict[str, Any]:
        name = _clean(values.get("name"), "Project name", limit=100)
        business_name = _clean(values.get("business_name"), "Business name", limit=100)
        city = _clean(values.get("city"), "City", required=False, limit=80)
        site_url = _clean(values.get("site_url"), "Main site URL")
        if not site_url.startswith(("http://", "https://")):
            raise AnalysisError("Main site URL must begin with http:// or https://.")
        created = _now()
        project = {
            "id": "proj-" + uuid4().hex[:12],
            "name": name,
            "business_name": business_name,
            "city": city,
            "site_url": site_url,
            "created_at": created,
            "updated_at": created,
            "audits": [],
            "connections": {},
        }
        with self._lock:
            records = self._records()
            records.append(project)
            self._write(self.projects_file, records)
        return deepcopy(project)

    def add_audit(self, project_id: str, result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(result, dict) or not isinstance(result.get("site"), dict):
            raise AnalysisError("A complete audit result is required.")
        audit_id = _clean(result.get("id"), "Audit ID", limit=100)
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", audit_id):
            raise AnalysisError("Audit ID contains unsupported characters.")
        summary = {
            "id": audit_id,
            "audit_type": result.get("audit_type", "page"),
            "score": int(result.get("score", 0)),
            "issue_count": len(result.get("issues", [])),
            "page_count": int(result.get("facts", {}).get("pages_analyzed", 1)),
            "created_at": _now(),
        }
        with self._lock:
            records = self._records()
            project = next((item for item in records if item.get("id") == project_id), None)
            if not project:
                raise AnalysisError("Unknown project.")
            audit_site = result.get("site", {})
            same_business = _clean(
                audit_site.get("business_name"), "Business name", required=False, limit=100
            ).casefold() == _clean(
                project.get("business_name"), "Business name", required=False, limit=100
            ).casefold()
            audit_host = (urlparse(str(audit_site.get("url", ""))).hostname or "").casefold()
            project_host = (urlparse(str(project.get("site_url", ""))).hostname or "").casefold()
            same_site = bool(audit_host and project_host and audit_host == project_host)
            if not same_business and not same_site:
                raise AnalysisError("This audit belongs to a different business or website.")
            project_dir = self.audits_dir / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            self._write(project_dir / f"{audit_id}.json", result)
            project["audits"] = [item for item in project.get("audits", []) if item.get("id") != audit_id]
            project["audits"].insert(0, summary)
            project["updated_at"] = _now()
            self._write(self.projects_file, records)
            return deepcopy(project)

    def get_audit(self, project_id: str, audit_id: str) -> dict[str, Any]:
        """Return a saved audit only when it belongs to the requested project."""
        audit_id = _clean(audit_id, "Audit ID", limit=100)
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", audit_id):
            raise AnalysisError("Unknown audit.")
        with self._lock:
            project = self.get_project(project_id)
            if not any(item.get("id") == audit_id for item in project.get("audits", [])):
                raise AnalysisError("Unknown audit.")
            audit = self._read(self.audits_dir / project_id / f"{audit_id}.json", None)
            if not isinstance(audit, dict):
                raise AnalysisError("The saved audit snapshot is unavailable.")
            return deepcopy(audit)

    def get_latest_audit(self, project_id: str) -> dict[str, Any] | None:
        project = self.get_project(project_id)
        audits = project.get("audits", [])
        return self.get_audit(project_id, audits[0]["id"]) if audits else None

    def set_connection(self, project_id: str, source: str, metadata: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            records = self._records()
            project = next((item for item in records if item.get("id") == project_id), None)
            if not project:
                raise AnalysisError("Unknown project.")
            project.setdefault("connections", {})[source] = metadata
            project["updated_at"] = _now()
            self._write(self.projects_file, records)
            return deepcopy(project)

    def save_google_token(self, project_id: str, source: str, token: dict[str, Any]) -> None:
        self.get_project(project_id)
        with self._lock:
            records = self._read(self.tokens_file, {})
            records.setdefault(project_id, {})[source] = token
            self._write(self.tokens_file, records, private=True)

    def get_google_token(self, project_id: str, source: str) -> dict[str, Any] | None:
        self.get_project(project_id)
        with self._lock:
            records = self._read(self.tokens_file, {})
            value = records.get(project_id, {}).get(source)
            return deepcopy(value) if isinstance(value, dict) else None

    def disconnect_google(self, project_id: str, source: str) -> dict[str, Any]:
        with self._lock:
            records = self._records()
            project = next((item for item in records if item.get("id") == project_id), None)
            if not project:
                raise AnalysisError("Unknown project.")
            project.setdefault("connections", {}).pop(source, None)
            project["updated_at"] = _now()
            self._write(self.projects_file, records)
            tokens = self._read(self.tokens_file, {})
            if project_id in tokens:
                tokens[project_id].pop(source, None)
                if not tokens[project_id]:
                    tokens.pop(project_id)
                self._write(self.tokens_file, tokens, private=True)
            return deepcopy(project)
