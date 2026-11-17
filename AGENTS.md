# Working in Codex Chess Harness

Start with the [README](README.md) for setup, commands, and the game-to-review workflow. See [agent readiness](docs/agent-readiness.md) for the repository design and verification boundaries.

When delegating during live collection, read the [subagent workflow](.codex/subagent-workflow.md) for UI ownership, parallel work, and the post-game handoff.

| Task | Entry point |
| --- | --- |
| Capture a board and record a visible action | [controller.mjs](controller.mjs) |
| Verify PGN and run Stockfish offline | [chesslab/evaluate.py](chesslab/evaluate.py) |
| Save a verified result and render its local report | [chesslab/archive.py](chesslab/archive.py) |
| Search or review a lesson in the local archive | [chesslab/patterns.py](chesslab/patterns.py) |

Run both [offline checks](README.md#verify-the-code) before sending a PR. Use synthetic evidence when testing. The controller records intent, action, observation and explicit readback. Inspect a fresh screenshot before retrying an uncertain click.

Live matchmaking requires explicit authorization for the run. Freeze the controller and player configuration before a game. During play use only visible screenshots and clicks. Keep the engine and archived lesson evidence outside the player context. Preserve incomplete attempts and apply the predeclared offline promotion rule before using candidate lessons live.

Keep screenshots, raw traces, PGNs, account details, databases and HTML reports under ignored `evidence/private/`. Review exactly what is staged before publishing source changes. Report live outcomes and offline engineering checks with their own evidence.
