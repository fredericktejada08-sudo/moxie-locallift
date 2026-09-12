import unittest

from locallift.analyzer import extract_facts
from locallift.claude import SYSTEM_PROMPT
from locallift.demo import DEMO_AI, get_demo_site
from locallift.rules import evaluate


def audit_demo(site_id: str):
    site = get_demo_site(site_id)
    facts = extract_facts(site["html"], site["url"], site["business_name"], site["city"], site["service"])
    score, issues = evaluate(facts, site["city"], site["service"])
    return score, issues


class RuleEngineTests(unittest.TestCase):
    def test_critical_issue_sorts_first(self):
        _, issues = audit_demo("northline")
        self.assertEqual(issues[0]["id"], "indexability.noindex")
        self.assertEqual(issues[0]["severity"], "critical")

    def test_everwell_has_evidence_bound_metadata_issues(self):
        score, issues = audit_demo("everwell")
        issue_ids = {issue["id"] for issue in issues}
        self.assertLess(score, 70)
        self.assertIn("local.city_title", issue_ids)
        self.assertIn("metadata.service_title", issue_ids)
        self.assertIn("metadata.description_missing", issue_ids)
        self.assertIn("schema.local_business_missing", issue_ids)

    def test_scores_remain_bounded(self):
        for site_id in ("everwell", "northline", "harbor"):
            score, _ = audit_demo(site_id)
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_healthy_demo_does_not_manufacture_work(self):
        score, issues = audit_demo("harbor")
        self.assertEqual(score, 100)
        self.assertEqual(issues, [])

    def test_reference_metadata_counts_are_exact(self):
        for result in DEMO_AI.values():
            metadata = result["metadata"]
            self.assertEqual(metadata["title_length"], len(metadata["title"]))
            self.assertEqual(metadata["description_length"], len(metadata["description"]))

    def test_ai_prompt_constrains_schema_and_claims(self):
        self.assertIn('"MedicalSpa" is not an allowed type', SYSTEM_PROMPT)
        self.assertIn("claims explicitly present in the facts", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
