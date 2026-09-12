import unittest

from locallift.claude import MAX_OUTPUT_TOKENS, _request_payload, _validate


class ClaudeValidationTests(unittest.TestCase):
    def test_request_has_completion_room_for_site_reports(self):
        payload = _request_payload({"site": {}, "facts": {}, "issues": []})

        self.assertEqual(payload["max_tokens"], MAX_OUTPUT_TOKENS)
        self.assertGreaterEqual(payload["max_tokens"], 4096)

    def test_removes_actions_without_real_evidence_ids(self):
        raw = {
            "executive_summary": "Summary",
            "priority_actions": [
                {"title": "Grounded", "why": "Why", "steps": "Steps", "evidence_ids": ["known", "made.up"]},
                {"title": "Ungrounded", "why": "Why", "steps": "Steps", "evidence_ids": ["made.up"]},
            ],
            "metadata": {"title": "Title", "description": "Description"},
            "human_checks": ["Check one"],
            "scale_note": "Scale note",
        }

        result = _validate(raw, {"known"})

        self.assertEqual(len(result["priority_actions"]), 1)
        self.assertEqual(result["priority_actions"][0]["evidence_ids"], ["known"])
        self.assertEqual(result["metadata"]["title_length"], 5)
        self.assertEqual(result["metadata"]["description_length"], 11)


if __name__ == "__main__":
    unittest.main()
