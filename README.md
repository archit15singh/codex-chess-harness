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
