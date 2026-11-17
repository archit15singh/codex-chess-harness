"""Record observed outcomes in local SQLite and render private game reports."""

import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sqlite3
import statistics
import tempfile

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    recorded_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    outcome TEXT NOT NULL,
    side TEXT NOT NULL,
    elo_before INTEGER,
    elo_after INTEGER,
    evaluation_sha256 TEXT,
    notes TEXT NOT NULL
) WITHOUT ROWID;
"""


def skill_rows(evaluation, side):
    if evaluation is None:
        return [("Offline evaluation", "No evaluated move record for this attempt.")]
    engine = evaluation["engine_analysis"]
    moves = [row for row in engine["rows"] if row["turn"] == side]
    losses = [row["cp_loss_nonnegative"] for row in moves if row["cp_loss_nonnegative"] is not None]
    missed = [
        f'{(row["ply"] + 1) // 2}. {row["san"]} (engine move {row["best"]["pv"][0]})'
        for row in moves
        if row["best"]["mate"] == 1 and row["selected"]["mate"] != 1
    ]
    median = statistics.median(losses) if losses else "unavailable"
    return [
        ("Move recording", f'{evaluation["plies"]} legal plies'),
        ("Clock and interaction", "Read the operator notes and private action log."),
        ("Forcing-move recognition", f'{len(missed)} missed mate-in-one positions. ' + ", ".join(missed)),
        ("Move quality", f'{len(losses)}/{len(moves)} moves with finite comparable scores. '
         f'Median nonnegative loss {median} cp.'),
        ("Conversion", evaluation["termination"] or "See the verified platform outcome."),
        ("Engine settings", f'{engine["engine_id"]["name"]}, {engine["nodes_per_search"]:,} nodes per search'),
    ]


def render(run_id, mode, outcome, before, after, notes, evaluation, side):
    rating = f"{before} → {after}" if before is not None and after is not None else "Unavailable"
    items = "".join(
        f"<tr><th scope='row'>{escape(label)}</th><td>{escape(value)}</td></tr>"
        for label, value in skill_rows(evaluation, side)
    )
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chess review · {escape(run_id)}</title>
<style>
:root {{ color-scheme: dark; background: #111816; color: #e9f1eb; font: 16px/1.6 system-ui, sans-serif; }}
body {{ max-width: 52rem; margin: 3rem auto; padding: 0 1rem; }}
h1, h2 {{ line-height: 1.2; }}
header p {{ color: #b3c8ba; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: .7rem; border-bottom: 1px solid #44564a; text-align: left; vertical-align: top; }}
td {{ overflow-wrap: anywhere; }}
strong {{ color: #abedab; }}
.notes {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
</style>
<main>
<header>
<h1>Chess review · {escape(run_id)}</h1>
<p>{escape(mode)} · {escape(outcome)} · <strong>Elo {escape(rating)}</strong></p>
</header>
<h2>Skills</h2>
<table><tbody>{items}</tbody></table>
<h2>Operator notes</h2>
<p class="notes">{escape(notes)}</p>
</main>
</html>
"""


def archive(root, run_id, mode, outcome, before, after, notes, evaluation_path, side):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id):
        raise ValueError("Use a run ID with lowercase letters, digits and hyphens")
    evaluation = None
    digest = None
    if evaluation_path:
        data = evaluation_path.read_bytes()
        evaluation = json.loads(data)
        digest = hashlib.sha256(data).hexdigest()
        if outcome == "incomplete" or evaluation["result_header"] != outcome:
            raise ValueError("Evaluation result disagrees with the platform outcome")

    html = render(run_id, mode, outcome, before, after, notes, evaluation, side)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = root / f"{run_id}.html"
    connection = sqlite3.connect(root / "sessions.sqlite")
    try:
        connection.execute(SCHEMA)
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            values = (mode, outcome, side, before, after, digest, notes)
            prior = connection.execute(
                "SELECT mode, outcome, side, elo_before, elo_after, evaluation_sha256, notes "
                "FROM sessions WHERE id = ?", (run_id,)
            ).fetchone()
            if prior is None:
                connection.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (run_id, datetime.now(timezone.utc).isoformat(), *values))
            elif prior != values or (destination.exists() and destination.read_text() != html):
                raise ValueError(f"Run {run_id} already has different evidence or annotations")
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=root, delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                try:
                    temporary.write(html)
                    temporary.flush()
                    temporary_path.replace(destination)
                finally:
                    temporary_path.unlink(missing_ok=True)
    finally:
        connection.close()
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--root", type=Path, default=Path("evidence/private/reviews"))
    parser.add_argument("--mode", required=True, choices=("Anyone", "Friend", "Oscar", "local"))
    parser.add_argument("--outcome", required=True, choices=("1-0", "0-1", "1/2-1/2", "incomplete"))
    parser.add_argument("--before", type=int)
    parser.add_argument("--after", type=int)
    parser.add_argument("--notes", required=True, type=Path)
    parser.add_argument("--evaluation", type=Path)
    parser.add_argument("--side", choices=("white", "black"), required=True)
    args = parser.parse_args()
    try:
        report = archive(args.root, args.run_id, args.mode, args.outcome, args.before, args.after,
                         args.notes.read_text(), args.evaluation, args.side)
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        parser.exit(2, f"archiving failed: {error}\n")
    print(report.resolve())


if __name__ == "__main__":
    main()
