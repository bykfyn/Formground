"""The paid-test arithmetic in scraper/insights_report.py (the SQL itself needs real BigQuery and is not run here)."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))

try:
    import insights_report as ir
    HAVE = True
except ImportError:
    HAVE = False


class FakeJob:
    def __init__(self, rows):
        self.rows = rows

    def result(self):
        return self.rows


class FakeClient:
    def __init__(self, rows):
        self.rows = rows

    def query(self, sql, job_config=None):
        return FakeJob(self.rows)


@unittest.skipUnless(HAVE, "google-cloud-bigquery not installed")
class PaidTestTests(unittest.TestCase):
    def test_verdict_follows_the_locked_thresholds(self):
        self.assertTrue(ir.verdict(29, 5).startswith("too few"))
        self.assertEqual(ir.verdict(30, 17), "CONTINUE")
        self.assertEqual(ir.verdict(30, 17.1), "ITERATE")
        self.assertEqual(ir.verdict(30, 31), "ITERATE")
        self.assertEqual(ir.verdict(30, 31.1), "CHANGE APPROACH")

    def run_paid(self, rows, csv_text):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write(csv_text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ir.paid_test(FakeClient(rows), "p.d.t", None, fh.name)
        return out.getvalue()

    def test_cost_per_outbound_click_and_overall_call(self):
        rows = [{"utm_source": "google", "utm_campaign": "chairs_work_202610", "visits": 100,
                 "visits_with_click": 40, "outbound_clicks": 50}]
        out = self.run_paid(rows, "campaign,spend_kr,week_start\nchairs_work_202610,500,2026-10-12\nchairs_work_202610,250,2026-10-19\n")
        self.assertIn("15.0", out)               # 750 kr / 50 clicks
        self.assertIn("CONTINUE", out)
        self.assertIn("40.0", out)               # outbound rate

    def test_unread_cells_are_not_called(self):
        rows = [{"utm_source": "pinterest", "utm_campaign": "vases_edits_202610", "visits": 20,
                 "visits_with_click": 5, "outbound_clicks": 8}]
        out = self.run_paid(rows, "campaign,spend_kr\nvases_edits_202610,250\n")
        self.assertIn("too few clicks to read", out)
        self.assertIn("no campaign has enough outbound clicks", out)

    def test_engaged_rate_and_capture_ratio(self):
        rows = [{"utm_source": "google", "utm_campaign": "c1", "visits": 80, "visits_with_click": 20,
                 "outbound_clicks": 24, "engaged_visits": 60}]
        out = self.run_paid(rows, "campaign,spend_kr,platform_clicks\nc1,400,100\n")
        self.assertIn("75.0", out)    # engaged: 60 / 80
        self.assertIn("80.0", out)    # captured: 80 visits / 100 platform clicks

    def test_campaign_without_a_spend_row_is_flagged(self):
        rows = [{"utm_source": "google", "utm_campaign": "mystery", "visits": 3, "visits_with_click": 1, "outbound_clicks": 1}]
        out = self.run_paid(rows, "campaign,spend_kr\nother,100\n")
        self.assertIn("no spend row in the CSV", out)
        self.assertIn("no outbound clicks yet", out)   # 'other' has spend but no clicks


if __name__ == "__main__":
    unittest.main()
