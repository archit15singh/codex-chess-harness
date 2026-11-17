"""Build a private annotated replay from a completed PGN and its action ledger."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path

import chess

from .compare import MOVE
from .evaluate import audit_actions, file_hash, parse_game


def replay_frames(pgn: Path, evaluation: Path, actions: Path, side: str) -> dict:
    game = parse_game(pgn.read_text(encoding="utf-8-sig"))
    if game.headers["Result"] == "*":
        raise ValueError("Replay requires a completed game")
    result = json.loads(evaluation.read_text())
    if result["pgn_sha256"] != file_hash(pgn):
        raise ValueError("Evaluation does not match the replay PGN")
    action_audit = audit_actions(actions)
    if result["screenshots"]["actions_sha256"] != action_audit["actions_sha256"]:
        raise ValueError("Evaluation does not match the action ledger")

    events = [json.loads(line) for line in actions.read_text().splitlines() if line.strip()]
    intents = {event["id"]: event for event in events if event["phase"] == "intent"}
    accepted = [
        event for event in events if event["phase"] == "verified"
        and event["status"] == "accepted" and MOVE.fullmatch(event["label"])
    ]
    trace_start = datetime.fromisoformat(events[0]["at"])
    player = chess.WHITE if side == "white" else chess.BLACK
    board = game.initial.copy()
    frames = [{"position": board.board_fen(), "move": "Starting position"}]
    engine_rows = result["engine_analysis"]["rows"]
    player_index = 0
    for ply, (move, score) in enumerate(zip(game.moves, engine_rows, strict=True), 1):
        if score["ply"] != ply or score["move"] != move.uci() or score["fen"] != board.fen():
            raise ValueError(f"Evaluation position does not match ply {ply}")
        san = board.san(move)
        number = f"{board.fullmove_number}{'.' if board.turn else '…'}"
        trace = None
        if board.turn == player:
            if player_index == len(accepted) or accepted[player_index]["label"] != move.uci():
                raise ValueError(f"Accepted action ledger does not match ply {ply}")
            action = accepted[player_index]
            intent = intents[action["id"]]
            observed = datetime.fromisoformat(intent["observedAt"])
            verified = datetime.fromisoformat(action["at"])
            elapsed = (verified - trace_start).total_seconds()
            latency = (verified - observed).total_seconds()
            if elapsed < 0 or latency < 0:
                raise ValueError(f"Action timing is inconsistent at ply {ply}")
            trace = {"elapsed": round(elapsed, 3), "latency": round(latency, 3)}
            player_index += 1
        board.push(move)
        frames.append({
            "position": board.board_fen(),
            "move": f"{number} {san}",
            "uci": move.uci(),
            "trace": trace,
            "loss": score["cp_loss_nonnegative"],
            "best_mate": score["best"]["mate"],
        })
    if player_index != len(accepted):
        raise ValueError("Action ledger contains additional accepted moves")
    return {"side": side, "result": game.headers["Result"], "frames": frames}


def build_replay(pgn: Path, evaluation: Path, actions: Path, side: str, output: Path) -> None:
    replay = replay_frames(pgn, evaluation, actions, side)
    template = Path(__file__).with_name("replay.html").read_text()
    # Script data cannot close its element. Only derived board and timing fields are emitted.
    payload = json.dumps(replay, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    content = template.replace("__REPLAY_DATA__", payload)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
        out.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pgn", type=Path)
    parser.add_argument("--evaluation", required=True, type=Path)
    parser.add_argument("--actions", required=True, type=Path)
    parser.add_argument("--side", required=True, choices=("white", "black"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        build_replay(args.pgn, args.evaluation, args.actions, args.side, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"replay failed: {error}\n")
    print("Wrote private annotated replay.")


if __name__ == "__main__":
    main()
