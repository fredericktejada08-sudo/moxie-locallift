"""Semrush keyword research and local volume history."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from locallift.analyzer import AnalysisError


KEYWORD_METRICS_URL = "https://api.semrush.com/apis/v4/keywords/v1/metrics"
MAX_BATCH_SIZE = 10
SUPPORTED_COUNTRIES = {"AU", "CA", "NZ", "PH", "UK", "US"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_keywords(values: Any) -> list[str]:
    if isinstance(values, str):
        candidates = values.splitlines()
    elif isinstance(values, list):
        candidates = values
    else:
        raise AnalysisError("Keywords must be supplied as a list or one per line.")
    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        keyword = re.sub(r"\s+", " ", str(candidate or "")).strip()
        if not keyword:
            continue
        if len(keyword) > 255:
            raise AnalysisError("Each keyword must be 255 characters or fewer.")
        identity = keyword.casefold()
        if identity not in seen:
            keywords.append(keyword)
            seen.add(identity)
    if not keywords:
        raise AnalysisError("Enter at least one keyword.")
    if len(keywords) > MAX_BATCH_SIZE:
        raise AnalysisError(f"Keyword research accepts up to {MAX_BATCH_SIZE} keywords per request.")
    return keywords


def normalize_country(value: Any) -> str:
    country = str(value or "US").strip().upper()
    if country not in SUPPORTED_COUNTRIES:
        raise AnalysisError("Choose a supported keyword database.")
    return country


class SemrushKeywordClient:
    """Retrieve current keyword metrics without exposing the API key."""

    @staticmethod
    def configured() -> bool:
        return bool(os.getenv("SEMRUSH_API_KEY", "").strip())

    @staticmethod
    def _key() -> str:
        key = os.getenv("SEMRUSH_API_KEY", "").strip()
        if not key:
            raise AnalysisError("Semrush keyword research is not configured.")
        return key

    def metrics(self, keyword: str, country: str) -> dict[str, Any]:
        keyword = normalize_keywords([keyword])[0]
        country = normalize_country(country)
        url = f"{KEYWORD_METRICS_URL}?{urlencode({'keyword': keyword, 'country': country})}"
        request = Request(url, headers={
            "Authorization": f"Apikey {self._key()}",
            "Accept": "application/json",
            "User-Agent": "LocalLift/1.3",
        })
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code == 401:
                message = "Semrush rejected the API key. Replace or rotate SEMRUSH_API_KEY."
            elif exc.code == 403:
                message = (
                    "This Semrush key does not have Keyword Reports access. "
                    "Enable Standard API access and API units for the key."
                )
            else:
                message = f"Semrush keyword research returned HTTP {exc.code}."
            raise AnalysisError(message) from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise AnalysisError(f"Semrush keyword research could not be reached: {exc}") from exc
        if not isinstance(payload, dict) or not payload.get("meta", {}).get("success"):
            detail = payload.get("error", {}).get("message", "Unexpected response") \
                if isinstance(payload, dict) else "Unexpected response"
            raise AnalysisError(f"Semrush keyword research returned an error: {detail}.")
        data = payload.get("data", {})
        meta = payload.get("meta", {})
        try:
            volume = int(data.get("search_volume", 0) or 0)
            cpc_usd = round(float(data.get("cpc", 0) or 0) / 100, 2)
        except (TypeError, ValueError) as exc:
            raise AnalysisError("Semrush returned invalid keyword metrics.") from exc
        return {
            "keyword": keyword,
            "country": country,
            "month": str(meta.get("month", "")),
            "search_volume": volume,
            "keyword_difficulty": data.get("keyword_difficulty"),
            "cpc_usd": cpc_usd,
            "competitive_density": data.get("competitive_density"),
            "intents": data.get("intents", []),
            "serp_features": data.get("serp_features", []),
            "trends": data.get("trends", []),
            "checked_at": _now(),
        }


class KeywordMonitorStore:
    """Persist keyword snapshots independently from business projects."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.path = data_dir / "keyword_monitor.json"
        self._lock = threading.RLock()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AnalysisError("Keyword monitoring data could not be read.") from exc
        if not isinstance(records, list):
            raise AnalysisError("Keyword monitoring data has an invalid format.")
        return records

    def _write(self, records: list[dict[str, Any]]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.data_dir, 0o700)
        except OSError:
            pass
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(records, indent=2, ensure_ascii=True), encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def _public(record: dict[str, Any]) -> dict[str, Any]:
        history = record.get("history", [])
        latest = history[-1] if history else {}
        previous = history[-2] if len(history) > 1 else None
        return {
            "id": record["id"],
            "keyword": record["keyword"],
            "country": record["country"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "latest": deepcopy(latest),
            "previous_search_volume": previous.get("search_volume") if previous else None,
            "snapshot_count": len(history),
        }

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            records = self._read()
            records.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
            return [self._public(record) for record in records]

    def get_many(self, record_ids: Any) -> list[dict[str, Any]]:
        if not isinstance(record_ids, list) or not record_ids:
            raise AnalysisError("Select at least one monitored keyword.")
        ids = [str(value) for value in record_ids]
        if len(ids) > MAX_BATCH_SIZE:
            raise AnalysisError(f"Refresh accepts up to {MAX_BATCH_SIZE} keywords at a time.")
        with self._lock:
            records = self._read()
            selected = [record for record in records if record.get("id") in ids]
        if len(selected) != len(set(ids)):
            raise AnalysisError("One or more monitored keywords could not be found.")
        return deepcopy(selected)

    def upsert(self, metrics: dict[str, Any]) -> dict[str, Any]:
        identity = f"{metrics['country']}\0{metrics['keyword'].casefold()}"
        record_id = "kw-" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
        with self._lock:
            records = self._read()
            record = next((item for item in records if item.get("id") == record_id), None)
            if record is None:
                record = {
                    "id": record_id,
                    "keyword": metrics["keyword"],
                    "country": metrics["country"],
                    "created_at": metrics["checked_at"],
                    "updated_at": metrics["checked_at"],
                    "history": [],
                }
                records.append(record)
            record["keyword"] = metrics["keyword"]
            record["updated_at"] = metrics["checked_at"]
            record.setdefault("history", []).append(deepcopy(metrics))
            record["history"] = record["history"][-24:]
            self._write(records)
            return self._public(record)

    def delete(self, record_id: str) -> None:
        with self._lock:
            records = self._read()
            remaining = [record for record in records if record.get("id") != record_id]
            if len(remaining) == len(records):
                raise AnalysisError("Monitored keyword not found.")
            self._write(remaining)


class KeywordMonitor:
    def __init__(self, store: KeywordMonitorStore, client: SemrushKeywordClient):
        self.store = store
        self.client = client

    def research(self, values: Any, country: Any) -> list[dict[str, Any]]:
        keywords = normalize_keywords(values)
        database = normalize_country(country)
        metrics = [self.client.metrics(keyword, database) for keyword in keywords]
        return [self.store.upsert(item) for item in metrics]

    def refresh(self, record_ids: Any) -> list[dict[str, Any]]:
        records = self.store.get_many(record_ids)
        metrics = [
            self.client.metrics(record["keyword"], record["country"])
            for record in records
        ]
        return [self.store.upsert(item) for item in metrics]
