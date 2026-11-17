# Codex Chess Harness

A repeatable workflow for screenshot-only chess in Brave, followed by local Stockfish review. The first documented Duolingo Anyone session ended in a checkmate win and an account rating change from 585 to 597. [Session record](https://github.com/archit15singh/codex-chess-lab/blob/main/session/README.md)

For repository navigation and contribution boundaries, start with [AGENTS.md](AGENTS.md).

## Play and verify

Use Duolingo’s visible Anyone route only within the platform and participant permission for the run. Keep assessments and Stockfish outside the player context during play.

1. Prepare a fresh, private evidence directory, a frozen copy of `controller.mjs`, and a native Brave CUA binding before matchmaking. Inspect the live UI before resuming a run or retrying a click.
2. Load the frozen module in the CUA JavaScript session. Pass the native Brave app binding and a new directory under the ignored `evidence/private/` directory to `createController`. Confirm screenshot capture works before starting.
3. Read an image returned by `observe()`. Choose the move from the screenshot, confirm the active clock and settled board, then call `click(label, source, destination)` with screenshot-derived coordinates. Promotion is a separately observed, labeled click.
4. Read the resulting screenshot and call `verify(status, observation, note)` with `accepted`, `rejected`, or `uncertain`. Capture a fresh frame if a click was interrupted or the board is still animating. The ledger stores screenshots by hash and only the agent interprets their contents.
5. Read the result screen and match history. Record both ratings when visible, retain incomplete attempts, and transcribe verified moves into a private PGN. Keep account and opponent details local.

Example using a previously bound native Brave app and coordinates derived from a current image.

```javascript
const { createController } = await import(frozenModuleUrl);
const controller = await createController(braveApp, newPrivateRunDirectory);
let frame = await controller.observe();
await nodeRepl.emitImage(frame.bytes);
// After inspecting the board and choosing the move:
frame = await controller.click(moveLabel, sourceSquare, destinationSquare);
await nodeRepl.emitImage(frame.bytes);
// After confirming the destination and turn:
await controller.verify('accepted', frame, 'Piece and turn change confirmed');
```

For an authorized live broadcast, follow the [Twitch streaming workflow](docs/live-stream.md).

## Review and archive

Prepare Python with `python3 -m venv .venv` and install `requirements-evaluator.txt` inside that environment. Use a local [Stockfish](https://github.com/official-stockfish/Stockfish) UCI executable.

```sh
.venv/bin/python -m chesslab.evaluate evidence/private/game-001.pgn \
  --output evidence/private/game-001-evaluation.json \
  --engine /path/to/stockfish --nodes 30000 --require-board-terminal

.venv/bin/python -m chesslab.archive game-001 --mode Anyone --side white \
  --outcome 1-0 --before 585 --after 597 \
  --notes evidence/private/game-001-notes.txt \
  --evaluation evidence/private/game-001-evaluation.json
```

For a platform adjudication such as resignation or timeout, verify the outcome on the platform before recording it. Omit `--require-board-terminal` only when the verified ending is external to the board. For incomplete attempts, archive with `--outcome incomplete` and omit the evaluation. The archive saves SQLite and a self-contained HTML report under `evidence/private/reviews/`. A controller ledger can be hash-checked by passing it to the evaluator with `--actions`.

For each iteration, write down one failure, one proposed strategy change and how to measure it. Compare the candidate with the frozen baseline on unseen positions using fresh player contexts and the same model, effort, inputs, and scoring. Seal both move selections before revealing engine answers. Report sample size, missing answers, accuracy, and timings. Promote changes only when the measured results support them. Account Elo is tracked as a platform outcome alongside the benchmark.

## Make a private annotated replay

Use a completed PGN, its audited action ledger, and the corresponding Stockfish evaluation. The exporter checks screenshot hashes and joins every accepted player move to the PGN in sequence. It reconstructs the board, shows Stockfish loss or mate scores, and displays player action times relative to the first ledger entry. Opponent moves come from the PGN and have no player readback timestamp.

```sh
.venv/bin/python -m chesslab.replay evidence/private/example-001.pgn \
  --evaluation evidence/private/example-001-evaluation.json \
  --actions evidence/private/example-001/actions.jsonl --side black \
  --output evidence/private/example-001/replay.html
open -a 'Brave Browser' "$PWD/evidence/private/example-001/replay.html"
```

Use the slider to inspect moves. Select **Render WebM**, keep the tab visible through the render, then save the file under `evidence/private/` for editing. The exported clip plays at a fixed pace with the observed timestamps in the captions. The viewer and video render a reconstructed board without the original screenshots, names, PGN headers, raw trace text, or absolute timestamps.

## Compare reasoning efforts

Keep an ordered JSON array under `evidence/private/` with one entry per archived attempt. Set `id` to its archive ID and `effort` to the setting verified in the host trace. Mark retrospective games with `historical: true`. Attach available evaluation and action logs using paths relative to the private root.

```json
[
  {
    "id": "example-001",
    "effort": "medium",
    "evaluation": "example-001-evaluation.json",
    "actions": "example-001/actions.jsonl"
  }
]
```

```sh
.venv/bin/python -m chesslab.compare evidence/private/manifest.json \
  > evidence/private/comparison.json
```

Optional `trace` fields are `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens`, and `duration_seconds`. Record how you derived them alongside the manifest. Cached input and reasoning output are subsets of the corresponding totals. The report retains missing measurements, tracks incomplete attempts, and shows the prospective subset. Screen-to-verification latency covers the last input screenshot through the operator's readback. It can include UI and model time. Compare only like-for-like engine settings and review the output before sharing aggregate results.

After a game ends and the ledger is closed, sample the player's local Codex rollout. Set the shell variables to the private rollout path and expected player model.

```sh
.venv/bin/python -m chesslab.trace_window evidence/private/example-001/actions.jsonl \
  "$player_rollout" --model "$player_model" --effort medium
```

Save the output privately and copy its `trace` object into the matching manifest entry. The CLI checks player settings and subtracts the latest cumulative sample strictly before the ledger window from the last sample inside it. Samples can straddle the opening boundary and miss usage after the last in-window sample. Keep that limitation with the measurement and leave unavailable values missing.

## Verify the code

The offline checks run with Node 24 and Python 3.13 in GitHub Actions. From the repository root, set up the environment and run both suites.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-evaluator.txt
node --test
.venv/bin/python -m unittest discover -s tests -v
```

## Save a reusable pattern

Turn a reviewed mistake or successful tactic into a short observation and decision rule. Store the pattern in the local archive database and link it to the game that supplied the evidence.

```sh
.venv/bin/python -m chesslab.patterns add 'Forcing move scan' \
  --cues 'Exposed king, few escape squares, long-range pieces nearby' \
  --rule 'Check forcing moves. Verify the escape squares and immediate captures before committing.' \
  --source-run game-001
.venv/bin/python -m chesslab.patterns find king --include-candidates
```

Once the rule meets the predeclared offline promotion criteria, record the verdict with `chesslab.patterns review NAME ready --evidence REPORT`. Use `rejected` for a rule whose test did not support adoption. Default search shows ready rules. Look them up between games and carry only the general rules into the next game. Engine output, matching positions, and suggested moves stay offline.
