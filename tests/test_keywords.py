import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from locallift.analyzer import AnalysisError
from locallift.keywords import (
    KeywordMonitor,
    KeywordMonitorStore,
    SemrushKeywordClient,
    normalize_keywords,
)


class SemrushKeywordClientTests(unittest.TestCase):
    @patch.dict(os.environ, {"SEMRUSH_API_KEY": "private-key"})
    def test_requests_keyword_metrics_with_api_key_header(self):
        response = io.BytesIO(json.dumps({
            "meta": {
                "success": True,
                "status_code": 200,
                "keyword": "laser hair removal austin",
                "country": "US",
                "month": "2026-09",
            },
            "data": {
                "search_volume": "720",
                "keyword_difficulty": 43,
                "cpc": "625",
                "competitive_density": 71,
                "intents": ["COMMERCIAL"],
                "serp_features": ["LOCAL_PACK"],
                "trends": [80, 82, 85],
            },
        }).encode("utf-8"))
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return response

        with patch("locallift.keywords.urlopen", side_effect=fake_urlopen):
            metrics = SemrushKeywordClient().metrics("laser hair removal austin", "us")

        request = captured["request"]
        query = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(query["keyword"], ["laser hair removal austin"])
        self.assertEqual(query["country"], ["US"])
        self.assertEqual(request.get_header("Authorization"), "Apikey private-key")
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(metrics["search_volume"], 720)
        self.assertEqual(metrics["cpc_usd"], 6.25)

    @patch.dict(os.environ, {"SEMRUSH_API_KEY": "private-key"})
    def test_permission_error_is_actionable_and_does_not_expose_key(self):
        error = HTTPError(
            "https://api.semrush.com/",
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"error":{"message":"Forbidden"}}'),
        )
        with patch("locallift.keywords.urlopen", side_effect=error):
            with self.assertRaises(AnalysisError) as raised:
                SemrushKeywordClient().metrics("med spa", "US")

        self.assertIn("Keyword Reports access", str(raised.exception))
        self.assertNotIn("private-key", str(raised.exception))


class KeywordMonitorStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = KeywordMonitorStore(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_preserves_volume_history_and_previous_value(self):
        first = {
            "keyword": "med spa austin",
            "country": "US",
            "search_volume": 500,
            "checked_at": "2026-08-01T00:00:00+00:00",
        }
        second = {**first, "search_volume": 590, "checked_at": "2026-09-01T00:00:00+00:00"}
        self.store.upsert(first)
        record = self.store.upsert(second)

        self.assertEqual(record["latest"]["search_volume"], 590)
        self.assertEqual(record["previous_search_volume"], 500)
        self.assertEqual(record["snapshot_count"], 2)

    def test_keyword_normalization_deduplicates_case_and_spacing(self):
        keywords = normalize_keywords([" Med   Spa ", "med spa", "Botox Austin"])
        self.assertEqual(keywords, ["Med Spa", "Botox Austin"])

    def test_failed_batch_does_not_save_partial_results(self):
        class FailingClient:
            def metrics(self, keyword, country):
                if keyword == "second keyword":
                    raise AnalysisError("Semrush failed.")
                return {
                    "keyword": keyword,
                    "country": country,
                    "search_volume": 100,
                    "checked_at": "2026-09-01T00:00:00+00:00",
                }

        monitor = KeywordMonitor(self.store, FailingClient())
        with self.assertRaises(AnalysisError):
            monitor.research(["first keyword", "second keyword"], "US")

        self.assertEqual(self.store.list(), [])


if __name__ == "__main__":
    unittest.main()
