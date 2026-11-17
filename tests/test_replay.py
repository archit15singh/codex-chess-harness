import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from chesslab.evaluate import evaluate, parse_game
from chesslab.replay import build_replay, replay_frames


class ReplayTests(unittest.TestCase):
    def test_replay_matches_player_action_order_without_exporting_raw_evidence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pgn = root / "game.pgn"
            pgn.write_text(
                '[White "private-player"]\n[Result "0-1"]\n\n'
                '1. f3 e5 2. g4 Qh4# 0-1\n'
            )
            shot = root / "raw.png"
            shot.write_bytes(b"synthetic screenshot")
            ref = {"file": shot.name, "sha256": hashlib.sha256(shot.read_bytes()).hexdigest()}
            actions = root / "actions.jsonl"
            rows = []
            for index, move in enumerate(("e7e5", "d8h4")):
                rows.extend([
                    {"phase": "intent", "id": index, "label": move, "pre": ref,
                     "at": "2026-01-01T00:00:01Z", "observedAt": "2026-01-01T00:00:00Z"},
                    {"phase": "verified", "id": index, "label": move, "status": "accepted",
                     "evidence": ref, "note": "private-notation",
                     "at": "2026-01-01T00:00:03Z"},
                ])
            actions.write_text("\n".join(map(json.dumps, rows)))
            game = parse_game(pgn.read_text())
            result = evaluate(pgn, actions=actions, require_board_terminal=True)
            board = game.initial.copy()
            evaluations = []
            for ply, move in enumerate(game.moves, 1):
                evaluations.append({"ply": ply, "move": move.uci(), "fen": board.fen(),
                                    "cp_loss_nonnegative": 4, "best": {"mate": None}})
                board.push(move)
            result["engine_analysis"] = {"rows": evaluations}
            evaluation = root / "evaluation.json"
            evaluation.write_text(json.dumps(result))
            frames = replay_frames(pgn, evaluation, actions, "black")["frames"]

            self.assertEqual(frames[-1]["move"], "2… Qh4#")
            self.assertIsNone(frames[1]["trace"])
            self.assertEqual(frames[2]["trace"], {"elapsed": 2, "latency": 3})
            output = root / "replay.html"
            build_replay(pgn, evaluation, actions, "black", output)
            for private_text in ("private-player", "private-notation", "raw.png", ref["sha256"]):
                self.assertNotIn(private_text, output.read_text())
            with self.assertRaisesRegex(ValueError, "ledger does not match ply"):
                replay_frames(pgn, evaluation, actions, "white")
            shot.write_bytes(b"changed screenshot")
            with self.assertRaisesRegex(ValueError, "screenshot hash mismatch"):
                replay_frames(pgn, evaluation, actions, "black")
