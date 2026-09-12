"""Incremental Google OAuth for project-level SEO data sources."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from locallift.analyzer import AnalysisError
from locallift.projects import ProjectStore


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
STATE_TTL_SECONDS = 10 * 60
CONNECTORS = {
    "gbp": {
        "label": "Google Business Profile",
        "short_label": "GBP",
        "scope": "https://www.googleapis.com/auth/business.manage",
    },
    "gsc": {
        "label": "Google Search Console",
        "short_label": "GSC",
        "scope": "https://www.googleapis.com/auth/webmasters.readonly",
    },
    "ga4": {
        "label": "Google Analytics 4",
        "short_label": "GA4",
        "scope": "https://www.googleapis.com/auth/analytics.readonly",
    },
}


class GoogleOAuth:
    def __init__(self, store: ProjectStore):
        self.store = store
        self._states: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def configured() -> bool:
        return GoogleOAuth.has_direct_client() or any(
            GoogleOAuth.has_oauth_client(source) for source in CONNECTORS
        )

    @staticmethod
    def has_direct_client() -> bool:
        return bool(os.getenv("GOOGLE_CLIENT_ID", "").strip() and os.getenv("GOOGLE_CLIENT_SECRET", "").strip())

    @staticmethod
    def _oauth_profile_path(source: str) -> str:
        prefix = f"GOOGLE_{source.upper()}"
        return (
            os.getenv(f"{prefix}_OAUTH_PROFILE_FILE", "").strip()
            or os.getenv(f"{prefix}_TOKEN_FILE", "").strip()
        )

    @staticmethod
    def _profile_client(source: str) -> dict[str, str] | None:
        path = GoogleOAuth._oauth_profile_path(source)
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as stream:
                profile = json.load(stream)
        except (OSError, json.JSONDecodeError):
            return None
        client_id = str(profile.get("client_id", "")).strip()
        client_secret = str(profile.get("client_secret", "")).strip()
        if not client_id or not client_secret:
            return None
        return {"client_id": client_id, "client_secret": client_secret}

    @staticmethod
    def has_oauth_client(source: str) -> bool:
        return GoogleOAuth.has_direct_client() or GoogleOAuth._profile_client(source) is not None

    @staticmethod
    def redirect_uri() -> str:
        return os.getenv(
            "GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8042/oauth/google/callback"
        ).strip()

    @staticmethod
    def profile_redirect_uri() -> str:
        port = os.getenv("LOCALLIFT_PORT", "8042").strip() or "8042"
        return os.getenv(
            "GOOGLE_OAUTH_PROFILE_REDIRECT_URI", f"http://localhost:{port}"
        ).strip().rstrip("/")

    @classmethod
    def _oauth_client(cls, source: str) -> dict[str, str]:
        if cls.has_direct_client():
            return {
                "client_id": os.environ["GOOGLE_CLIENT_ID"].strip(),
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"].strip(),
                "redirect_uri": cls.redirect_uri(),
            }
        profile = cls._profile_client(source)
        if profile:
            return {**profile, "redirect_uri": cls.profile_redirect_uri()}
        connector = cls._connector(source)
        raise AnalysisError(
            f"Google OAuth is not configured for {connector['short_label']}. "
            "Add a Google OAuth client or an OAuth profile file to .env."
        )

    @staticmethod
    def _connector(source: str) -> dict[str, str]:
        connector = CONNECTORS.get(source)
        if not connector:
            raise AnalysisError("Unknown Google data source.")
        return connector

    def statuses(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        connected = project.get("connections", {})
        return [{
            "id": source,
            "label": connector["label"],
            "short_label": connector["short_label"],
            "configured": self.has_oauth_client(source),
            "connected": source in connected,
            "connected_at": connected.get(source, {}).get("connected_at"),
            "scope": connector["scope"],
        } for source, connector in CONNECTORS.items()]

    def authorization_url(self, project_id: str, source: str, app_origin: str = "") -> str:
        self.store.get_project(project_id)
        connector = self._connector(source)
        client = self._oauth_client(source)
        state = secrets.token_urlsafe(32)
        with self._lock:
            now = time.time()
            self._states = {
                key: value for key, value in self._states.items()
                if now - value["created_at"] < STATE_TTL_SECONDS
            }
            self._states[state] = {
                "project_id": project_id,
                "source": source,
                "created_at": now,
                "app_origin": app_origin,
                **client,
            }
        query = urlencode({
            "client_id": client["client_id"],
            "redirect_uri": client["redirect_uri"],
            "response_type": "code",
            "scope": connector["scope"],
            "access_type": "offline",
            "prompt": "consent select_account",
            "state": state,
        })
        return f"{AUTH_URL}?{query}"

    def _pop_pending(self, state: str) -> dict[str, Any]:
        with self._lock:
            pending = self._states.pop(state, None)
        if not pending or time.time() - pending["created_at"] >= STATE_TTL_SECONDS:
            raise AnalysisError("The Google authorization request expired or has already been used.")
        return pending

    def pending_context(self, state: str) -> tuple[str, str, str]:
        with self._lock:
            pending = self._states.get(state)
            if not pending or time.time() - pending["created_at"] >= STATE_TTL_SECONDS:
                return "", "", ""
            return pending["project_id"], pending["source"], pending.get("app_origin", "")

    def cancel(self, state: str) -> tuple[str, str, str]:
        pending = self._pop_pending(state)
        return pending["project_id"], pending["source"], pending.get("app_origin", "")

    def complete(self, state: str, code: str) -> tuple[str, str, str]:
        pending = self._pop_pending(state)
        project_id = pending["project_id"]
        source = pending["source"]
        connector = self._connector(source)
        request = Request(
            TOKEN_URL,
            method="POST",
            data=urlencode({
                "code": code,
                "client_id": pending["client_id"],
                "client_secret": pending["client_secret"],
                "redirect_uri": pending["redirect_uri"],
                "grant_type": "authorization_code",
            }).encode("utf-8"),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                token = json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise AnalysisError(f"Google token exchange returned HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise AnalysisError(f"Google token exchange failed: {exc}") from exc
        if not token.get("access_token"):
            raise AnalysisError("Google did not return an access token.")
        existing = self.store.get_google_token(project_id, source) or {}
        if not token.get("refresh_token") and existing.get("refresh_token"):
            token["refresh_token"] = existing["refresh_token"]
        token.update({
            "client_id": pending["client_id"],
            "client_secret": pending["client_secret"],
            "token_uri": TOKEN_URL,
        })
        token["saved_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.store.save_google_token(project_id, source, token)
        metadata = {
            "connected_at": token["saved_at"],
            "scope": connector["scope"],
            "token_type": token.get("token_type", "Bearer"),
            "authorization_source": "interactive",
        }
        self.store.set_connection(project_id, source, metadata)
        return project_id, source, pending.get("app_origin", "")

    def disconnect(self, project_id: str, source: str) -> dict[str, Any]:
        self._connector(source)
        return self.store.disconnect_google(project_id, source)
