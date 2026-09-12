import unittest

from locallift.exporters import build_pdf


class PdfExportTests(unittest.TestCase):
    def test_builds_downloadable_pdf(self):
        result = {
            "audit_type": "page",
            "site": {"business_name": "Example MedSpa", "city": "Austin", "service": "Facials", "url": "https://example.com/facials"},
            "score": 78,
            "facts": {"indexable": True},
            "issues": [{
                "id": "metadata.description_missing", "severity": "high", "title": "Meta description is missing",
                "evidence": "description length: 0", "recommendation": "Write a supported description.",
            }],
            "ai": {"status": "not_requested", "mode": "none"},
        }
        pdf = build_pdf(result)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 1000)

    def test_rejects_incomplete_result(self):
        with self.assertRaises(ValueError):
            build_pdf({})


if __name__ == "__main__":
    unittest.main()

