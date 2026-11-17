"""Summarize the private effort comparison from archived games and trace measurements."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sqlite3
from statistics import median

from .evaluate import file_hash


MOVE = re.compile(r"[a-h][1-8][a-h][1-8][qrbn]?")
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")


def evidence_path(root: Path, name: str) -> Path:
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Evidence must be a file under the private root: {name}")
    return path


def timing_summary(path: Path, expected_moves: list[str] | None) -> dict:
    intents = {}
    accepted_moves = []
    latencies = []
    counts = Counter()
    for line in path.read_text().splitlines():
        event = json.loads(line)
        action = event["id"]
        phase = event["phase"]
        if phase == "intent":
            intents[action] = event
        if phase != "verified":
            continue
        intent = intents[action]
        label = intent["label"]
        if MOVE.fullmatch(label) is None:
            continue
        verdict = event["status"]
        counts[verdict] += 1
        if verdict == "accepted":
            accepted_moves.append(label)
            observed = datetime.fromisoformat(intent["observedAt"])
            verified = datetime.fromisoformat(event["at"])
            seconds = (verified - observed).total_seconds()
            if seconds < 0:
                raise ValueError("Move verification precedes its input screenshot")
            latencies.append(seconds)
        del intents[action]
    counts["unverified"] = sum(MOVE.fullmatch(e["label"]) is not None for e in intents.values())
    if expected_moves is not None and accepted_moves != expected_moves:
        raise ValueError("Accepted action moves disagree with the evaluated player moves")
    return {
        "move_verdicts": dict(counts),
        "screen_to_verification_seconds": numeric_summary(latencies),
    }


def numeric_summary(values) -> dict:
    observed = [value for value in values if value is not None]
    return {"count": len(observed), "median": median(observed) if observed else None}


def game_summary(root: Path, record: dict, archived: sqlite3.Row) -> dict:
    if record["effort"] not in {"medium", "low"}:
        raise ValueError("Effort must be medium or low")
    if type(record.get("historical", False)) is not bool:
        raise ValueError("Historical must be a boolean")
    if archived["mode"] != "Anyone":
        raise ValueError("Comparison games must use Anyone mode")
    result = archived["outcome"]
    before, after = archived["elo_before"], archived["elo_after"]
    row = {
        "effort": record["effort"], "historical": record.get("historical", False),
        "outcome": result, "side": archived["side"], "elo_before": before,
        "elo_after": after, "elo_change": after - before if None not in (before, after) else None,
    }
    moves = None
    if "evaluation" in record:
        path = evidence_path(root, record["evaluation"])
        if file_hash(path) != archived["evaluation_sha256"]:
            raise ValueError("Evaluation digest disagrees with the archive")
        evaluation = json.loads(path.read_text())
        engine = evaluation["engine_analysis"]
        rows = [item for item in engine["rows"] if item["turn"] == row["side"]]
        moves = [item["move"] for item in rows]
        row["quality"] = {
            "player_moves": len(moves),
            "finite_loss_cp": numeric_summary(item["cp_loss_nonnegative"] for item in rows),
            "mate_in_one_available": sum(item["best"]["mate"] == 1 for item in rows),
            "mate_in_one_missed": sum(
                item["best"]["mate"] == 1 and item["selected"]["mate"] != 1 for item in rows
            ),
            "winning_mate_dropped": sum(
                (item["best"]["mate"] or 0) > 0 and (item["selected"]["mate"] or 0) <= 0
                for item in rows
            ),
            "engine": {key: engine[key] for key in (
                "binary_sha256", "nodes_per_search", "hash_reset_each_search", "options"
            )},
        }
        row["actions_sha256"] = (evaluation.get("screenshots") or {}).get("actions_sha256")
    if "actions" in record:
        path = evidence_path(root, record["actions"])
        digest = row.pop("actions_sha256", None)
        if digest is not None and file_hash(path) != digest:
            raise ValueError("Action ledger digest disagrees with the evaluation")
        row["interaction"] = timing_summary(path, moves)
    else:
        row.pop("actions_sha256", None)
    row["trace"] = {}
    for key in (*TOKEN_FIELDS, "duration_seconds"):
        value = record.get("trace", {}).get(key)
        if value is not None:
            expected = (int, float) if key == "duration_seconds" else (int,)
            if type(value) not in expected or value < 0 or not math.isfinite(value):
                raise ValueError(f"Invalid trace measurement: {key}")
        row["trace"][key] = value
    return row


def cohort(rows: list[dict]) -> dict:
    verdicts = Counter()
    for row in rows:
        verdicts.update(row.get("interaction", {}).get("move_verdicts", {}))
    quality = [row["quality"] for row in rows if "quality" in row]
    return {
        "attempts": len(rows),
        "completed": sum(row["outcome"] != "incomplete" for row in rows),
        "results": dict(Counter(
            "win" if (row["outcome"], row["side"]) in {("1-0", "white"), ("0-1", "black")}
            else {"1-0": "loss", "0-1": "loss", "1/2-1/2": "draw", "incomplete": "incomplete"}[row["outcome"]]
            for row in rows
        )),
        "elo_change": numeric_summary(row["elo_change"] for row in rows),
        "evaluated_games": len(quality),
        "game_median_finite_loss_cp": numeric_summary(
            game["finite_loss_cp"]["median"] for game in quality
        ),
        "finite_loss_moves": sum(game["finite_loss_cp"]["count"] for game in quality),
        "evaluated_moves": sum(game["player_moves"] for game in quality),
        "mate_in_one_available": sum(game["mate_in_one_available"] for game in quality),
        "mate_in_one_missed": sum(game["mate_in_one_missed"] for game in quality),
        "winning_mate_dropped": sum(game["winning_mate_dropped"] for game in quality),
        "games_with_action_logs": sum("interaction" in row for row in rows),
        "move_verdicts": dict(verdicts),
        "game_median_screen_to_verification_seconds": numeric_summary(
            row["interaction"]["screen_to_verification_seconds"]["median"]
            for row in rows if "interaction" in row
        ),
        "trace": {key: numeric_summary(row["trace"][key] for row in rows)
                  for key in (*TOKEN_FIELDS, "duration_seconds")},
    }


def summarize(root: Path, manifest: Path) -> dict:
    root = root.resolve(strict=True)
    records = json.loads(manifest.read_text())
    database = evidence_path(root, "reviews/sessions.sqlite")
    rows = []
    identifiers = set()
    low_started = False
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        for record in records:
            run = record["id"]
            if run in identifiers:
                raise ValueError(f"Duplicate manifest run: {run}")
            identifiers.add(run)
            archived = connection.execute("SELECT * FROM sessions WHERE id = ?", (run,)).fetchone()
            if archived is None:
                raise ValueError(f"Game missing from archive: {run}")
            row = game_summary(root, record, archived)
            if low_started and row["effort"] == "medium":
                raise ValueError("A medium game follows a low game in the manifest")
            low_started |= row["effort"] == "low"
            rows.append(row)
    engines = {json.dumps(row["quality"]["engine"], sort_keys=True)
               for row in rows if "quality" in row}
    return {
        "engine_settings_uniform": len(engines) == 1 if engines else None,
        "all_games": {effort: cohort([row for row in rows if row["effort"] == effort])
                      for effort in ("medium", "low")},
        "prospective_games": {
            effort: cohort([row for row in rows if row["effort"] == effort and not row["historical"]])
            for effort in ("medium", "low")
        },
        "games_in_manifest_order": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path("evidence/private"))
    args = parser.parse_args()
    try:
        print(json.dumps(summarize(args.root, args.manifest), indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        parser.exit(2, f"comparison failed: {error}\n")


if __name__ == "__main__":
    main()
