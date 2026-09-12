#!/usr/bin/env python3
"""LocalLift's dependency-free local web server and JSON API."""

from __future__ import annotations

import json
import hashlib
import mimetypes
import os
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from locallift import __version__
from locallift.analyzer import AnalysisError, extract_facts, fetch_html
from locallift.claude import ClaudeError, configured, synthesize
from locallift.crawler import crawl_site
from locallift.demo import DEMO_AI, DEMO_SITES, get_demo_site
from locallift.exporters import build_pdf
from locallift.google_oauth import GoogleOAuth
from locallift.keywords import KeywordMonitor, KeywordMonitorStore, SemrushKeywordClient
from locallift.project_dashboard import build_project_dashboard
from locallift.projects import ProjectStore
from locallift.rules import evaluate


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
MAX_REQUEST_BYTES = 2_000_000


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE settings without adding a runtime dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


load_dotenv(ROOT / ".env")
DATA_DIR = Path(os.getenv("LOCALLIFT_DATA_DIR", ROOT / ".data")).expanduser().resolve()
PROJECT_STORE = ProjectStore(DATA_DIR)
GOOGLE_OAUTH = GoogleOAuth(PROJECT_STORE)
KEYWORD_STORE = KeywordMonitorStore(DATA_DIR)
SEMRUSH_KEYWORDS = KeywordMonitor(KEYWORD_STORE, SemrushKeywordClient())


def project_payload(project: dict[str, Any]) -> dict[str, Any]:
    return {**project, "connectors": GOOGLE_OAUTH.statuses(project)}


def local_app_origin() -> str:
    port = os.getenv("LOCALLIFT_PORT", "8042").strip() or "8042"
    return f"http://127.0.0.1:{port}"


def oauth_result_page(
    success: bool,
    message: str,
    project_id: str = "",
    source: str = "",
    target_origin: str = "",
) -> str:
    target_origin = target_origin or local_app_origin()
    payload = json.dumps({
        "type": "locallift-google-oauth",
        "success": success,
        "message": message,
        "project_id": project_id,
        "source": source,
    }).replace("</", "<\\/")
    post_message_origin = json.dumps(target_origin)
    return_url = f"{target_origin.rstrip('/')}/"
    title = "Connection complete" if success else "Connection failed"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title} | LocalLift</title><style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f7f6;color:#17201d;
font:14px system-ui,sans-serif}}main{{width:min(420px,calc(100% - 32px));padding:28px;background:white;
border:1px solid #dce3df;border-radius:6px}}h1{{margin:0 0 10px;font-size:20px}}p{{margin:0;color:#66716d;
line-height:1.5}}a{{display:inline-block;margin-top:18px;color:#087b70;font-weight:700}}</style></head>
<body><main><h1>{title}</h1><p id="message"></p><a href="{return_url}">Return to LocalLift</a></main>
<script>const result={payload};document.querySelector('#message').textContent=result.message;
if(window.opener){{window.opener.postMessage(result,{post_message_origin});window.setTimeout(()=>window.close(),700);}}</script>
</body></html>"""


def analyze_site(site: dict[str, Any], use_ai: bool = False) -> dict[str, Any]:
    business_name = str(site.get("business_name", "")).strip()
    city = str(site.get("city", "")).strip()
    service = str(site.get("service", "")).strip()
    url = str(site.get("url", "")).strip()
    if not all((business_name, city, service, url)):
        raise AnalysisError("Business name, city, primary service, and URL are all required.")
    if any(len(value) > 250 for value in (business_name, city, service, url)):
        raise AnalysisError("One or more fields exceed the 250-character limit.")

    demo_id = str(site.get("demo_id", "")).strip()
    if demo_id:
        try:
            demo = get_demo_site(demo_id)
        except KeyError as exc:
            raise AnalysisError("Unknown demo site.") from exc
        html = demo["html"]
        fetch = {
            "requested_url": demo["url"],
            "final_url": demo["url"],
            "status": 200,
            "content_type": "text/html",
            "bytes": len(html.encode("utf-8")),
        }
        source_mode = "offline_demo"
    else:
        html, fetch = fetch_html(url)
        source_mode = "live_fetch"

    site_context = {
        "business_name": business_name,
        "city": city,
        "service": service,
        "url": fetch["final_url"],
    }
    facts = extract_facts(html, fetch["final_url"], business_name, city, service)
    score, issues = evaluate(facts, city, service)
    result: dict[str, Any] = {
        "audit_type": "page",
        "id": demo_id or "page-" + hashlib.sha1(fetch["final_url"].encode("utf-8")).hexdigest()[:10],
        "site": site_context,
        "source": {"mode": source_mode, **fetch},
        "score": score,
        "issues": issues,
        "facts": facts,
        "ai": {"status": "not_requested", "mode": "none"},
    }

    if demo_id and not use_ai:
        result["ai"] = {
            "status": "complete",
            "mode": "reference_demo",
            "model": "reference output (offline)",
            "usage": {},
            "result": DEMO_AI[demo_id],
        }
    elif use_ai:
        try:
            result["ai"] = synthesize(site_context, facts, issues)
        except ClaudeError as exc:
            result["ai"] = {"status": "unavailable", "mode": "live", "error": str(exc)}
    return result


class LocalLiftHandler(BaseHTTPRequestHandler):
    server_version = f"LocalLift/{__version__}"

    def log_message(self, message: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {message % args}")

    def _json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _download(self, body: bytes, content_type: str, filename: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, markup: str, status: int = HTTPStatus.OK) -> None:
        body = markup.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise AnalysisError("Invalid request length.") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise AnalysisError("Request body must be JSON and smaller than 2 MB.")
        try:
            body = self.rfile.read(length)
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AnalysisError("Request body is not valid JSON.") from exc
        if not isinstance(value, dict):
            raise AnalysisError("Request body must be a JSON object.")
        return value

    def _app_origin(self) -> str:
        host = self.headers.get("Host", "").strip().lower()
        if re.fullmatch(r"(?:localhost|127\.0\.0\.1)(?::\d{1,5})?", host):
            return f"http://{host}"
        return local_app_origin()

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        target = (STATIC / relative).resolve()
        if STATIC not in target.parents or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self._json({
                "ok": True,
                "version": __version__,
                "ai_configured": configured(),
                "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5") if configured() else None,
                "google_oauth_configured": GOOGLE_OAUTH.configured(),
                "semrush_configured": SEMRUSH_KEYWORDS.client.configured(),
            })
        elif path == "/api/projects":
            self._json({
                "projects": [project_payload(project) for project in PROJECT_STORE.list_projects()],
                "google_oauth_configured": GOOGLE_OAUTH.configured(),
            })
        elif match := re.fullmatch(r"/api/projects/(proj-[a-f0-9]{12})/dashboard", path):
            try:
                project = PROJECT_STORE.get_project(match.group(1))
                requested_audit_id = parse_qs(parsed.query).get("audit_id", [""])[0]
                if requested_audit_id:
                    audit = PROJECT_STORE.get_audit(match.group(1), requested_audit_id)
                else:
                    audits = project.get("audits", [])
                    primary = next(
                        (item for item in audits if item.get("audit_type") == "site"),
                        audits[0] if audits else None,
                    )
                    audit = PROJECT_STORE.get_audit(match.group(1), primary["id"]) if primary else None
                self._json({"dashboard": build_project_dashboard(project, audit)})
            except AnalysisError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        elif path == "/api/keywords":
            self._json({
                "records": KEYWORD_STORE.list(),
                "semrush_configured": SEMRUSH_KEYWORDS.client.configured(),
                "max_batch_size": 10,
                "units_per_keyword": 20,
            })
        elif match := re.fullmatch(r"/api/projects/(proj-[a-f0-9]{12})/google/connect", path):
            source = parse_qs(parsed.query).get("source", [""])[0]
            try:
                authorization_url = GOOGLE_OAUTH.authorization_url(
                    match.group(1), source, self._app_origin()
                )
                self._json({"authorization_url": authorization_url, "connection_mode": "oauth"})
            except AnalysisError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        elif path == "/oauth/google/callback" or (
            path == "/" and parse_qs(parsed.query).get("state")
            and (parse_qs(parsed.query).get("code") or parse_qs(parsed.query).get("error"))
        ):
            query = parse_qs(parsed.query)
            state = query.get("state", [""])[0]
            code = query.get("code", [""])[0]
            error = query.get("error", [""])[0]
            project_id, source, target_origin = GOOGLE_OAUTH.pending_context(state)
            if error:
                if state:
                    try:
                        project_id, source, target_origin = GOOGLE_OAUTH.cancel(state)
                    except AnalysisError:
                        pass
                self._html(oauth_result_page(
                    False,
                    f"Google authorization was not completed: {error}.",
                    project_id,
                    source,
                    target_origin,
                ))
            elif not state or not code:
                self._html(oauth_result_page(
                    False,
                    "The Google callback did not include the required authorization details.",
                    target_origin=target_origin,
                ), HTTPStatus.BAD_REQUEST)
            else:
                try:
                    project_id, source, target_origin = GOOGLE_OAUTH.complete(state, code)
                    label = next(item["label"] for item in GOOGLE_OAUTH.statuses(PROJECT_STORE.get_project(project_id)) if item["id"] == source)
                    self._html(oauth_result_page(
                        True,
                        f"{label} is authorized for this project.",
                        project_id,
                        source,
                        target_origin,
                    ))
                except AnalysisError as exc:
                    self._html(oauth_result_page(
                        False, str(exc), project_id, source, target_origin
                    ), HTTPStatus.BAD_REQUEST)
        elif path == "/api/demo":
            results = [analyze_site({**site, "demo_id": site["id"]}) for site in DEMO_SITES]
            self._json({"results": results})
        else:
            self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/analyze":
                self._json(analyze_site(body, bool(body.get("use_ai", False))))
            elif path == "/api/crawl":
                self._json(crawl_site(body, bool(body.get("use_ai", False))))
            elif path == "/api/synthesize":
                result = body.get("result")
                if not isinstance(result, dict) or not isinstance(result.get("issues"), list):
                    raise AnalysisError("A complete audit result is required for AI synthesis.")
                try:
                    result["ai"] = synthesize(
                        result.get("site", {}), result.get("facts", {}), result["issues"][:30]
                    )
                except ClaudeError as exc:
                    result["ai"] = {"status": "unavailable", "mode": "live", "error": str(exc)}
                self._json(result)
            elif path == "/api/export/pdf":
                result = body.get("result", body if isinstance(body.get("site"), dict) else None)
                try:
                    pdf = build_pdf(result)
                except ValueError as exc:
                    raise AnalysisError(str(exc)) from exc
                business = str(result.get("site", {}).get("business_name", "audit"))
                slug = "-".join(re.findall(r"[a-z0-9]+", business.casefold())) or "audit"
                self._download(pdf, "application/pdf", f"{slug}-locallift-audit.pdf")
            elif path == "/api/projects":
                self._json({"project": project_payload(PROJECT_STORE.create_project(body))}, HTTPStatus.CREATED)
            elif match := re.fullmatch(r"/api/projects/(proj-[a-f0-9]{12})/audits", path):
                result = body.get("result")
                self._json({"project": project_payload(PROJECT_STORE.add_audit(match.group(1), result))})
            elif match := re.fullmatch(r"/api/projects/(proj-[a-f0-9]{12})/google/disconnect", path):
                source = str(body.get("source", "")).strip()
                project = GOOGLE_OAUTH.disconnect(match.group(1), source)
                self._json({"project": project_payload(project)})
            elif path == "/api/keywords/research":
                updated = SEMRUSH_KEYWORDS.research(body.get("keywords"), body.get("country"))
                self._json({"records": KEYWORD_STORE.list(), "updated": updated})
            elif path == "/api/keywords/refresh":
                updated = SEMRUSH_KEYWORDS.refresh(body.get("ids"))
                self._json({"records": KEYWORD_STORE.list(), "updated": updated})
            elif path == "/api/keywords/delete":
                KEYWORD_STORE.delete(str(body.get("id", "")))
                self._json({"records": KEYWORD_STORE.list()})
            elif path == "/api/batch":
                sites = body.get("sites", [])
                if not isinstance(sites, list) or not 1 <= len(sites) <= 10:
                    raise AnalysisError("Batch mode accepts between 1 and 10 sites.")
                use_ai = bool(body.get("use_ai", False))
                indexed_results: dict[int, dict[str, Any]] = {}
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {
                        executor.submit(analyze_site, site, use_ai): index
                        for index, site in enumerate(sites)
                    }
                    for future in as_completed(futures):
                        index = futures[future]
                        try:
                            indexed_results[index] = {"ok": True, "result": future.result()}
                        except AnalysisError as exc:
                            indexed_results[index] = {"ok": False, "error": str(exc)}
                self._json({"results": [indexed_results[index] for index in range(len(sites))]})
            else:
                self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
        except AnalysisError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            self._json({"error": "Unexpected server error."}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    host = os.getenv("LOCALLIFT_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("LOCALLIFT_PORT", "8042"))
    except ValueError:
        print("LOCALLIFT_PORT must be an integer.", file=sys.stderr)
        raise SystemExit(2)
    server = ThreadingHTTPServer((host, port), LocalLiftHandler)
    print(f"LocalLift {__version__} running at http://{host}:{port}")
    print(f"Claude synthesis: {'configured' if configured() else 'not configured (rules + demo still work)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LocalLift.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
