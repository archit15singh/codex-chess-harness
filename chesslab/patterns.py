"""Keep post-game lessons and their offline validation in the private archive."""

import argparse
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS patterns (
    name TEXT PRIMARY KEY,
    cues TEXT NOT NULL,
    rule TEXT NOT NULL,
    source_run TEXT NOT NULL REFERENCES sessions(id),
    status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'ready', 'rejected')),
    review_sha256 TEXT
) WITHOUT ROWID;
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("evidence/private/reviews/sessions.sqlite"))
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("name")
    add.add_argument("--cues", required=True)
    add.add_argument("--rule", required=True)
    add.add_argument("--source-run", required=True)
    find = commands.add_parser("find")
    find.add_argument("query", nargs="?", default="")
    find.add_argument("--include-candidates", action="store_true")
    review = commands.add_parser("review")
    review.add_argument("name")
    review.add_argument("verdict", choices=("ready", "rejected"))
    review.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    try:
        database = args.db.resolve(strict=True).as_uri() + "?mode=rw"
        with closing(sqlite3.connect(database, uri=True)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(SCHEMA)
            if args.command == "add":
                connection.execute(
                    "INSERT INTO patterns (name, cues, rule, source_run) VALUES (?, ?, ?, ?)",
                    (args.name, args.cues, args.rule, args.source_run),
                )
            elif args.command == "review":
                evidence = args.evidence.read_bytes()
                if not evidence.strip():
                    raise ValueError("Review evidence is empty")
                changed = connection.execute(
                    "UPDATE patterns SET status = ?, review_sha256 = ? "
                    "WHERE name = ? AND status = 'candidate'",
                    (args.verdict, hashlib.sha256(evidence).hexdigest(), args.name),
                )
                if changed.rowcount != 1:
                    raise ValueError("Expected an existing unreviewed pattern")
            else:
                words = args.query.casefold().split()
                for row in connection.execute("SELECT * FROM patterns ORDER BY name"):
                    if row["status"] != "ready" and not args.include_candidates:
                        continue
                    searchable = " ".join(row[key] for key in ("name", "cues", "rule")).casefold()
                    if all(word in searchable for word in words):
                        print(f'{row["name"]} [{row["status"]}]\n'
                              f'  Cues — {row["cues"]}\n  Rule — {row["rule"]}\n'
                              f'  Source — {row["source_run"]}')
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(2, f"pattern index: {error}\n")


if __name__ == "__main__":
    main()
