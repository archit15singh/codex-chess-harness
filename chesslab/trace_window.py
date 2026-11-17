"""Measure a closed game's local Codex rollout without copying raw trace data."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from datetime import datetime
import json
from pathlib import Path


USAGE_KEYS = {
    "input_tokens": "input_tokens",
    "cached_input_tokens": "cached_input_tokens",
    "output_tokens": "output_tokens",
    "reasoning_tokens": "reasoning_output_tokens",
}


def rows(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as stream:
        for index, line in enumerate(stream, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {index}") from error
            if not isinstance(record, dict):
                raise ValueError(f"Expected an object on line {index}")
            yield record


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid measurement timestamp") from error
    if result.utcoffset() is None:
        raise ValueError("Measurement timestamps must include a timezone")
    return result


def ledger_window(actions: Path) -> tuple[datetime, datetime]:
    records = iter(rows(actions))
    first = next(records, None)
    if first is None or first["phase"] != "intent":
        raise ValueError("Action ledger must start with an intent")
    start = previous = timestamp(first["at"])
    last = first
    for record in records:
        at = timestamp(record["at"])
        if at < previous:
            raise ValueError("Action ledger timestamps are out of order")
        previous, last = at, record
    if last["phase"] != "verified":
        raise ValueError("Action ledger must end with a verified action")
    return start, previous


def usage_totals(info: dict) -> dict[str, int]:
    totals = info["total_token_usage"]
    result = {field: totals[key] for field, key in USAGE_KEYS.items()}
    if any(type(total) is not int or total < 0 for total in result.values()):
        raise ValueError("Invalid cumulative token totals")
    if result["cached_input_tokens"] > result["input_tokens"] or (
        result["reasoning_tokens"] > result["output_tokens"]
    ):
        raise ValueError("Token subsets exceed their cumulative totals")
    return result


def measure(actions: Path, rollout: Path, model: str, effort: str) -> dict:
    start, end = ledger_window(actions)
    expected = (model, effort)
    setting = None
    baseline = latest = None
    previous_at = None
    for row in rows(rollout):
        at = timestamp(row["timestamp"])
        if previous_at is not None and at < previous_at:
            raise ValueError("Rollout timestamps are out of order")
        previous_at = at
        if at > end:
            break
        payload = row["payload"]
        if row["type"] == "turn_context":
            setting = (payload.get("model"), payload.get("effort"))
        if at >= start and setting != expected:
            raise ValueError("Rollout model or reasoning effort differs from the expected setting")
        if row["type"] != "event_msg" or payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        if info is None:
            continue
        totals = usage_totals(info)
        if at < start:
            baseline = (at, totals)
            continue
        previous = latest or baseline
        if previous and any(totals[key] < previous[1][key] for key in USAGE_KEYS):
            raise ValueError("Rollout cumulative token totals reset during the game window")
        latest = (at, totals)

    if baseline is None or latest is None:
        raise ValueError("Need token samples before the first action and within the game window")
    before_at, before = baseline
    last_at, last = latest
    delta = {key: last[key] - before[key] for key in USAGE_KEYS}
    if delta["cached_input_tokens"] > delta["input_tokens"] or (
        delta["reasoning_tokens"] > delta["output_tokens"]
    ):
        raise ValueError("Token subsets exceed their measured deltas")
    return {
        "model": model,
        "effort": effort,
        "trace": {
            **delta,
            "duration_seconds": (end - start).total_seconds(),
        },
        "ledger_start": start.isoformat(),
        "ledger_end": end.isoformat(),
        "sample_start": before_at.isoformat(),
        "sample_end": last_at.isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("actions", type=Path, help="closed action ledger")
    parser.add_argument("rollout", type=Path, help="local Codex rollout JSONL for the player")
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True, choices=("medium", "low"))
    args = parser.parse_args()
    try:
        report = measure(args.actions, args.rollout, args.model, args.effort)
    except (OSError, TypeError, ValueError, KeyError) as error:
        parser.exit(1, f"Trace measurement failed: {error}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
