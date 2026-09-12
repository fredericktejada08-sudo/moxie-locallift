import unittest

from locallift.project_dashboard import build_project_dashboard


class ProjectDashboardTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            "audits": [{"id": "site-one", "created_at": "2026-09-11T00:00:00+00:00"}],
        }
        self.issue = {
            "id": "metadata.title",
            "severity": "high",
            "title": "Title needs work",
            "impact": "Searchers cannot identify the service.",
            "recommendation": "Lead with the service name.",
            "effort": "Low",
            "affected_count": 2,
            "affected_pages": [{
                "url": "https://example.com/service",
                "page_title": "Service",
                "page_type": "service",
                "page_score": 72,
            }],
        }

    def test_joins_claude_action_to_issue_evidence(self):
        audit = {
            "id": "site-one", "audit_type": "site", "score": 72,
            "facts": {"pages_analyzed": 4}, "issues": [self.issue],
            "ai": {"status": "complete", "result": {
                "executive_summary": "Fix the title template first.",
                "priority_actions": [{
                    "title": "Rewrite service titles",
                    "why": "The current titles are ambiguous.",
                    "steps": "Update the shared template.",
                    "evidence_ids": ["metadata.title"],
                }],
                "human_checks": ["Confirm the preferred service wording."],
                "scale_note": "Use the shared template.",
            }},
        }

        dashboard = build_project_dashboard(self.project, audit)

        self.assertEqual(dashboard["recommendation_source"], "claude")
        self.assertEqual(dashboard["actions"][0]["severity"], "high")
        self.assertEqual(dashboard["actions"][0]["affected_count"], 2)
        self.assertEqual(dashboard["actions"][0]["affected_pages"][0]["url"], "https://example.com/service")
        self.assertEqual(dashboard["human_checks"], ["Confirm the preferred service wording."])

    def test_falls_back_to_rule_recommendations_without_ai(self):
        audit = {
            "id": "site-one", "audit_type": "site", "score": 72,
            "facts": {"pages_analyzed": 4}, "issues": [self.issue],
            "ai": {"status": "not_requested"},
        }

        dashboard = build_project_dashboard(self.project, audit)

        self.assertEqual(dashboard["recommendation_source"], "audit")
        self.assertEqual(dashboard["actions"][0]["title"], "Title needs work")
        self.assertEqual(dashboard["actions"][0]["steps"], "Lead with the service name.")

    def test_empty_project_prompts_for_an_audit(self):
        dashboard = build_project_dashboard({"audits": []}, None)
        self.assertIsNone(dashboard["audit"])
        self.assertEqual(dashboard["actions"], [])


if __name__ == "__main__":
    unittest.main()
