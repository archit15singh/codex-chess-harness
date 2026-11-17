import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from chesslab.archive import archive
from chesslab.compare import summarize, timing_summary


class ComparisonTests(unittest.TestCase):
    def test_incomplete_attempt_and_missing_trace_remain_visible(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive(root / "reviews", "trial", "Anyone", "incomplete",
                    None, None, "", None, "black")
            manifest = root / "manifest.json"
            manifest.write_text('[{"id":"trial","effort":"medium","historical":true}]')

            report = summarize(root, manifest)
            medium = report["all_games"]["medium"]
            self.assertEqual(medium["results"], {"incomplete": 1})
            self.assertEqual(medium["completed"], 0)
            self.assertEqual(medium["trace"]["input_tokens"], {"count": 0, "median": None})
            self.assertEqual(report["prospective_games"]["medium"]["attempts"], 0)
            self.assertEqual(report["all_games"]["low"]["attempts"], 0)

    def test_action_summary_counts_retries_and_checks_accepted_order(self):
        with TemporaryDirectory() as directory:
            now = "2026-01-01T00:00:00+00:00"
            later = "2026-01-01T00:00:03+00:00"
            rows = [
                {"id": "1", "phase": "intent", "observedAt": now, "label": "e2e3"},
                {"id": "1", "phase": "verified", "status": "rejected", "at": later},
                {"id": "2", "phase": "intent", "observedAt": now, "label": "e2e4"},
                {"id": "2", "phase": "verified", "status": "accepted", "at": later},
                {"id": "3", "phase": "intent", "observedAt": later, "label": "g1f3"},
                {"id": "4", "phase": "intent", "observedAt": later, "label": "Continue"},
            ]
            log = Path(directory) / "actions.jsonl"
            log.write_text("\n".join(json.dumps(row) for row in rows))
            report = timing_summary(log, ["e2e4"])
            self.assertEqual(report["move_verdicts"], {"accepted": 1, "rejected": 1, "unverified": 1})
            self.assertEqual(report["screen_to_verification_seconds"], {"count": 1, "median": 3})
            with self.assertRaisesRegex(ValueError, "disagree"):
                timing_summary(log, ["e2e3"])

    def test_promotion_picker_counts_as_an_action_but_not_an_extra_pgn_move(self):
        with TemporaryDirectory() as directory:
            log = Path(directory) / "actions.jsonl"
            rows = [
                {"id": "1", "phase": "intent", "label": "a7a8",
                 "observedAt": "2026-01-01T00:00:00Z"},
                {"id": "1", "phase": "verified", "status": "accepted",
                 "at": "2026-01-01T00:00:02Z"},
                {"id": "2", "phase": "intent", "label": "a7a8n",
                 "observedAt": "2026-01-01T00:00:03Z"},
                {"id": "2", "phase": "verified", "status": "rejected",
                 "at": "2026-01-01T00:00:04Z"},
                {"id": "3", "phase": "intent", "label": "a7a8q",
                 "observedAt": "2026-01-01T00:00:05Z"},
                {"id": "3", "phase": "verified", "status": "accepted",
                 "at": "2026-01-01T00:00:11Z"},
            ]
            log.write_text("\n".join(json.dumps(row) for row in rows))
            report = timing_summary(log, ["a7a8q"])
            self.assertEqual(report["move_verdicts"], {"accepted": 2, "rejected": 1, "unverified": 0})
            self.assertEqual(report["screen_to_verification_seconds"], {"count": 2, "median": 4})

            rows[-2]["label"] = "b7b8q"
            log.write_text("\n".join(json.dumps(row) for row in rows))
            with self.assertRaisesRegex(ValueError, "disagree"):
                timing_summary(log, ["b7b8q"])
