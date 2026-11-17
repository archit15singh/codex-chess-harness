import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from chesslab.archive import archive


class ArchiveTests(unittest.TestCase):
    def test_incomplete_run_is_idempotent_and_notes_are_escaped(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = (root, "pilot-001", "Anyone", "incomplete", None, None, "<private>", None, "white")
            report = archive(*args)
            self.assertEqual(archive(*args), report)
            self.assertIn("&lt;private&gt;", report.read_text())
            with sqlite3.connect(root / "sessions.sqlite") as conn:
                self.assertEqual(conn.execute("SELECT outcome FROM sessions").fetchall(), [("incomplete",)])
            with self.assertRaisesRegex(ValueError, "different evidence"):
                archive(*args[:-1], "black")

    def test_evaluation_must_agree_with_the_verified_platform_result(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluation = root / "evaluation.json"
            evaluation.write_text('{"result_header":"0-1"}')
            with self.assertRaisesRegex(ValueError, "disagrees"):
                archive(root, "game-001", "Anyone", "1-0", None, None, "", evaluation, "white")
            self.assertFalse((root / "sessions.sqlite").exists())
