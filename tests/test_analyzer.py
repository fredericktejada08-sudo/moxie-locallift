import unittest

from locallift.analyzer import AnalysisError, _assert_public_url, extract_facts
from locallift.demo import get_demo_site


class ExtractFactsTests(unittest.TestCase):
    def test_extracts_local_page_signals(self):
        site = get_demo_site("harbor")
        facts = extract_facts(
            site["html"], site["url"], site["business_name"], site["city"], site["service"]
        )

        self.assertEqual(facts["h1_count"], 1)
        self.assertTrue(facts["indexable"])
        self.assertTrue(facts["has_local_business_schema"])
        self.assertTrue(facts["has_address_schema"])
        self.assertTrue(facts["city_in_title"])
        self.assertTrue(facts["service_in_h1"])
        self.assertTrue(facts["has_phone_link"])
        self.assertEqual(facts["images_without_alt"], 0)

    def test_flags_noindex_and_missing_canonical(self):
        site = get_demo_site("northline")
        facts = extract_facts(
            site["html"], site["url"], site["business_name"], site["city"], site["service"]
        )

        self.assertFalse(facts["indexable"])
        self.assertIn("noindex", facts["robots"])
        self.assertEqual(facts["canonical"], "")

    def test_invalid_json_ld_is_counted_without_crashing(self):
        html = '<html><head><script type="application/ld+json">{"broken":</script></head><body><h1>Test</h1></body></html>'
        facts = extract_facts(html, "https://example.com", "Example", "Austin", "Facials")
        self.assertEqual(facts["invalid_json_ld_blocks"], 1)

    def test_private_and_credentialed_urls_are_rejected(self):
        with self.assertRaises(AnalysisError):
            _assert_public_url("http://127.0.0.1/admin")
        with self.assertRaises(AnalysisError):
            _assert_public_url("https://user:password@example.com/")

    def test_invalid_port_has_user_facing_error(self):
        with self.assertRaisesRegex(AnalysisError, "invalid port"):
            _assert_public_url("https://example.com:not-a-port/")


if __name__ == "__main__":
    unittest.main()
