import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from chesslab.trace_window import measure


def at(second):
    return f"2026-01-01T00:00:{second:02d}Z"


def context(second, model="fixture-model", effort="medium"):
    return {"timestamp": at(second), "type": "turn_context",
            "payload": {"model": model, "effort": effort}}


def usage(second, input_tokens, cached, output, reasoning):
    return {"timestamp": at(second), "type": "event_msg", "payload": {
        "type": "token_count",
        "info": {"total_token_usage": {
            "input_tokens": input_tokens,
            "cached_input_tokens": cached,
            "output_tokens": output,
            "reasoning_output_tokens": reasoning,
        }},
    }}


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


class TraceWindowTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.actions = root / "actions.jsonl"
        self.rollout = root / "rollout.jsonl"
        self.start = {"at": at(10), "phase": "intent"}
        self.end = {"at": at(20), "phase": "verified"}
        write_rows(self.actions, [self.start, self.end])
        self.context = context(1)
        self.baseline = usage(9, 150, 100, 25, 5)
        self.latest = usage(20, 300, 225, 45, 11)
        self.after = usage(21, 700, 225, 65, 16)

    def test_cli_reports_the_sampled_window_without_raw_records(self):
        write_rows(self.rollout, [
            self.context, usage(8, 100, 50, 10, 3), self.baseline,
            {"timestamp": at(10), "type": "response_item",
             "payload": {"text": "private fixture marker"}},
            usage(12, 175, 115, 26, 5), self.latest, self.after,
        ])
        run = subprocess.run(
            [sys.executable, "-m", "chesslab.trace_window", str(self.actions),
             str(self.rollout), "--model", "fixture-model", "--effort", "medium"],
            check=True, text=True, capture_output=True,
        )
        self.assertEqual(json.loads(run.stdout), {
            "model": "fixture-model",
            "effort": "medium",
            "trace": {"input_tokens": 150, "cached_input_tokens": 125,
                      "output_tokens": 20, "reasoning_tokens": 6, "duration_seconds": 10.0},
            "ledger_start": "2026-01-01T00:00:10+00:00",
            "ledger_end": "2026-01-01T00:00:20+00:00",
            "sample_start": "2026-01-01T00:00:09+00:00",
            "sample_end": "2026-01-01T00:00:20+00:00",
        })

    def test_missing_or_changed_player_settings_invalidate_the_window(self):
        for settings in ([], [self.context, context(15, effort="low")],
                         [self.context, context(15, model="other-model")]):
            with self.subTest(settings=settings):
                rows = sorted([*settings, self.baseline, self.latest],
                              key=lambda row: row["timestamp"])
                write_rows(self.rollout, rows)
                with self.assertRaisesRegex(ValueError, "model or reasoning effort"):
                    measure(self.actions, self.rollout, "fixture-model", "medium")

    def test_open_ledger_and_missing_usage_brackets_are_rejected(self):
        write_rows(self.actions, [self.start, {"at": at(11), "phase": "clicked"}])
        with self.assertRaisesRegex(ValueError, "end with a verified"):
            measure(self.actions, self.rollout, "fixture-model", "medium")

        write_rows(self.actions, [self.start, self.end])
        for rows in ([self.context, self.latest], [self.context, self.baseline, self.after]):
            with self.subTest(rows=rows):
                write_rows(self.rollout, rows)
                with self.assertRaisesRegex(ValueError, "Need token samples"):
                    measure(self.actions, self.rollout, "fixture-model", "medium")

    def test_rollout_order_resets_and_inconsistent_deltas_are_rejected(self):
        cases = (
            ([self.latest, usage(15, 350, 250, 50, 12)], "timestamps are out of order"),
            ([usage(15, 10, 5, 5, 1), self.latest], "totals reset"),
            ([usage(15, 200, 175, 45, 11)], "subsets exceed their measured deltas"),
            ([usage(15, 200, 225, 45, 11)], "subsets exceed their cumulative totals"),
        )
        for window, error in cases:
            with self.subTest(error=error):
                write_rows(self.rollout, [self.context, self.baseline, *window])
                with self.assertRaisesRegex(ValueError, error):
                    measure(self.actions, self.rollout, "fixture-model", "medium")
