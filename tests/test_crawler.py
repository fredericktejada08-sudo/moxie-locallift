import unittest
from unittest.mock import patch

from locallift.crawler import (
    _aggregate_issues,
    classify_page,
    discover_urls,
    is_applicable_url,
    topic_from_url,
)


class CrawlDiscoveryTests(unittest.TestCase):
    def test_classifies_common_local_site_pages(self):
        self.assertEqual(classify_page("https://example.com/"), "homepage")
        self.assertEqual(classify_page("https://example.com/services/laser-hair-removal"), "service")
        self.assertEqual(classify_page("https://example.com/blog/aftercare"), "article")
        self.assertEqual(classify_page("https://example.com/locations/austin"), "location")
        self.assertEqual(classify_page("https://example.com/contact"), "contact")
        self.assertEqual(topic_from_url("https://example.com/laser-hair-removal"), "Laser Hair Removal")

    def test_excludes_assets_and_utility_pages(self):
        self.assertFalse(is_applicable_url("https://example.com/brochure.pdf"))
        self.assertFalse(is_applicable_url("https://example.com/privacy-policy"))
        self.assertFalse(is_applicable_url("https://example.com/blog/page/2"))
        self.assertTrue(is_applicable_url("https://example.com/services/botox"))

    @patch("locallift.crawler.fetch_text")
    @patch("locallift.crawler.fetch_html")
    def test_discovers_sitemap_and_homepage_links(self, fetch_html_mock, fetch_text_mock):
        fetch_html_mock.return_value = (
            '<html><body><a href="/contact">Contact</a><a href="/privacy-policy">Privacy</a></body></html>',
            {"final_url": "https://example.com/", "status": 200, "bytes": 100, "content_type": "text/html"},
        )

        def text_response(url, *args, **kwargs):
            if url.endswith("robots.txt"):
                return "Sitemap: https://example.com/sitemap.xml", {"final_url": url}
            return (
                "<urlset><url><loc>https://example.com/services/laser-hair-removal</loc></url>"
                "<url><loc>https://example.com/brochure.pdf</loc></url></urlset>",
                {"final_url": url},
            )

        fetch_text_mock.side_effect = text_response
        urls, discovery, _, _ = discover_urls("https://example.com", 10)

        self.assertEqual(urls[0], "https://example.com/")
        self.assertIn("https://example.com/services/laser-hair-removal", urls)
        self.assertIn("https://example.com/contact", urls)
        self.assertNotIn("https://example.com/privacy-policy", urls)
        self.assertEqual(discovery["method"], "sitemap + homepage links")


class CrawlAggregationTests(unittest.TestCase):
    def test_groups_same_issue_across_pages(self):
        issue = {
            "id": "metadata.description_missing", "category": "Metadata", "severity": "high",
            "title": "Meta description is missing", "finding": "Missing.", "evidence": "length: 0",
            "impact": "Impact", "recommendation": "Add one.", "effort": "Low", "confidence": "High",
            "weight": 10,
        }
        pages = [
            {"url": "https://example.com/a", "page_type": "service", "score": 70, "facts": {"title": "A"}, "issues": [issue]},
            {"url": "https://example.com/b", "page_type": "service", "score": 75, "facts": {"title": "B"}, "issues": [issue]},
        ]
        grouped = _aggregate_issues(pages)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["affected_count"], 2)
        self.assertEqual(len(grouped[0]["affected_pages"]), 2)


if __name__ == "__main__":
    unittest.main()

