import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from locallift.google_oauth import GoogleOAuth
from locallift.projects import ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_creates_project_and_saves_audit_snapshot(self):
        project = self.store.create_project({
            "name": "Austin rollout",
            "business_name": "Everwell MedSpa",
            "city": "Austin",
            "site_url": "https://example.com",
        })
        updated = self.store.add_audit(project["id"], {
            "id": "site-example",
            "audit_type": "site",
            "site": {"business_name": "Everwell MedSpa"},
            "score": 82,
            "issues": [{"id": "metadata.title"}],
            "facts": {"pages_analyzed": 10},
        })

        self.assertEqual(updated["audits"][0]["score"], 82)
        self.assertEqual(updated["audits"][0]["page_count"], 10)
        snapshot = Path(self.temp.name) / "audits" / project["id"] / "site-example.json"
        self.assertTrue(snapshot.exists())
        self.assertEqual(self.store.get_latest_audit(project["id"])["score"], 82)

    def test_audit_cannot_be_read_through_another_project(self):
        first = self.store.create_project({
            "name": "First", "business_name": "First", "city": "",
            "site_url": "https://first.example",
        })
        second = self.store.create_project({
            "name": "Second", "business_name": "Second", "city": "",
            "site_url": "https://second.example",
        })
        self.store.add_audit(first["id"], {
            "id": "first-audit", "site": {"business_name": "First"},
            "score": 90, "issues": [], "facts": {},
        })

        with self.assertRaisesRegex(Exception, "Unknown audit"):
            self.store.get_audit(second["id"], "first-audit")

    def test_rejects_an_audit_for_a_different_business_and_site(self):
        project = self.store.create_project({
            "name": "Muse", "business_name": "Muse MedSpa", "city": "Austin",
            "site_url": "https://muse.example",
        })

        with self.assertRaisesRegex(Exception, "different business"):
            self.store.add_audit(project["id"], {
                "id": "other-audit", "site": {
                    "business_name": "Other MedSpa", "url": "https://other.example/service",
                },
                "score": 80, "issues": [], "facts": {},
            })

    def test_google_tokens_are_separate_from_public_project_data(self):
        project = self.store.create_project({
            "name": "Project",
            "business_name": "Business",
            "city": "",
            "site_url": "https://example.com",
        })
        self.store.save_google_token(project["id"], "gsc", {"access_token": "private-token"})
        self.store.set_connection(project["id"], "gsc", {"connected_at": "2026-09-10T00:00:00+00:00"})

        public = self.store.get_project(project["id"])
        self.assertNotIn("access_token", json.dumps(public))
        self.assertEqual(self.store.get_google_token(project["id"], "gsc")["access_token"], "private-token")
        self.assertEqual((Path(self.temp.name) / "google_tokens.json").stat().st_mode & 0o777, 0o600)


class GoogleOAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp.name))
        self.project = self.store.create_project({
            "name": "Project",
            "business_name": "Business",
            "city": "Austin",
            "site_url": "https://example.com",
        })
        self.oauth = GoogleOAuth(self.store)

    def tearDown(self):
        self.temp.cleanup()

    @patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "client-id", "GOOGLE_CLIENT_SECRET": "client-secret"})
    def test_requests_only_the_selected_connector_scope(self):
        authorization_url = self.oauth.authorization_url(self.project["id"], "gsc")
        query = parse_qs(urlparse(authorization_url).query)

        self.assertEqual(query["scope"], ["https://www.googleapis.com/auth/webmasters.readonly"])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent select_account"])
        self.assertNotIn("include_granted_scopes", query)

    @patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "client-id", "GOOGLE_CLIENT_SECRET": "client-secret"})
    def test_callback_stores_token_and_exposes_status_only(self):
        authorization_url = self.oauth.authorization_url(self.project["id"], "ga4")
        state = parse_qs(urlparse(authorization_url).query)["state"][0]
        response = io.BytesIO(json.dumps({
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/analytics.readonly",
            "token_type": "Bearer",
        }).encode("utf-8"))

        with patch("locallift.google_oauth.urlopen", return_value=response):
            project_id, source, app_origin = self.oauth.complete(state, "authorization-code")

        self.assertEqual((project_id, source), (self.project["id"], "ga4"))
        self.assertEqual(app_origin, "")
        project = self.store.get_project(project_id)
        status = next(item for item in self.oauth.statuses(project) if item["id"] == "ga4")
        self.assertTrue(status["connected"])
        self.assertNotIn("access", json.dumps(status))

    def test_existing_profile_still_opens_interactive_authorization(self):
        profile_path = Path(self.temp.name) / "existing-gsc.json"
        profile_path.write_text(json.dumps({
            "token": "expired",
            "refresh_token": "refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "scopes": ["https://www.googleapis.com/auth/webmasters.readonly"],
        }), encoding="utf-8")
        with patch.dict(os.environ, {
            "GOOGLE_GSC_OAUTH_PROFILE_FILE": str(profile_path),
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
        }, clear=False), patch("locallift.google_oauth.urlopen") as mocked_urlopen:
            authorization_url = self.oauth.authorization_url(
                self.project["id"], "gsc", "http://127.0.0.1:8042"
            )

        query = parse_qs(urlparse(authorization_url).query)
        self.assertEqual(query["client_id"], ["client-id"])
        self.assertEqual(query["redirect_uri"], ["http://localhost:8042"])
        self.assertEqual(query["scope"], ["https://www.googleapis.com/auth/webmasters.readonly"])
        self.assertEqual(query["prompt"], ["consent select_account"])
        mocked_urlopen.assert_not_called()
        self.assertNotIn("gsc", self.store.get_project(self.project["id"])["connections"])


if __name__ == "__main__":
    unittest.main()
