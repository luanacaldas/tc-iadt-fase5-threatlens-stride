from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendDetectionAlternativeTests(unittest.TestCase):
    def test_javascript_round_trip_contract(self) -> None:
        result = subprocess.run(
            ["node", "--test", "tests/test_detection_alternatives.mjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dashboard_renders_alternatives_without_promotion_controls(self) -> None:
        html = (ROOT / "app/index.html").read_text(encoding="utf-8")
        start = html.index('<table class="review-table alternative-review-table">')
        end = html.index("</table>", start)
        table = html[start:end]

        self.assertIn('id="alternativeReviewBody"', table)
        self.assertNotIn("<button", table)
        self.assertNotIn("<input", table)
        self.assertNotIn("<select", table)

    def test_review_pages_allow_generated_inline_assets_without_weakening_app_csp(self) -> None:
        server = (ROOT / "server.mjs").read_text(encoding="utf-8")

        self.assertIn('const reviewPathPrefix = "/data/reviews/tl004-junction-aware/";', server)
        self.assertIn("url.pathname.startsWith(reviewPathPrefix)", server)
        self.assertIn(
            '"Content-Security-Policy": "default-src \'self\'; img-src \'self\' blob: data:; '
            "style-src 'self'; script-src 'self'; connect-src 'self'\"",
            server,
        )
        self.assertIn(
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'",
            server,
        )


if __name__ == "__main__":
    unittest.main()
