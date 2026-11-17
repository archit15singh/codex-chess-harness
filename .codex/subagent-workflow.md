# Delegate work around live games

Use this runbook when the user requests subagents during a collection run. The player owns matchmaking, the Brave window, every move, and platform result and Elo verification. The player uses screenshots and visible clicks under the frozen protocol. Workers use text, shell, and web-search tools and leave desktop apps, browser tabs, and the live controller alone.

## Send work that can run independently

OpenAI recommends starting with bounded, read-heavy assignments such as research, triage, and test review. Give each agent a clear output and tell it when the parent needs the result. Parallel work can shorten elapsed time and reduce clutter in the parent context, but adds model and tool usage. Use `/subagents` in the interactive CLI to inspect or steer workers between games. [OpenAI subagent guide](https://learn.chatgpt.com/docs/agent-configuration/subagents)

| Timing | Work to delegate | Inputs and outputs |
| --- | --- | --- |
| Before queueing | Start public-source research, docs edits, isolated harness changes, or synthetic tests | Public sources, source commit, named paths and checks |
| After a verified ending | Run offline PGN verification, Stockfish review, and archive | Closed ledger, verified outcome and Elo, and PGN for that game only. Return only success or failure and private artifact paths |
| After collection | Analyze both cohorts, run held-out experiments, and generate requested walkthrough assets | Archived evidence under `evidence/private/`. Publish only approved sanitized outputs |

Keep one writer per set of paths and serialize writes to the SQLite archive and study manifest. Use a separate Git worktree for workers that need branch operations or shared-file edits. A worktree isolates the checkout. File and network access depend on the sandbox and permission settings inherited by the worker. Keep ignored evidence out of worktree copies and use synthetic fixtures for source changes. [OpenAI worktree guide](https://learn.chatgpt.com/docs/environments/git-worktrees) · [OpenAI subagent permissions](https://learn.chatgpt.com/docs/agent-configuration/subagents#approvals-and-sandbox-controls)

## Brief and hand back the work

Dispatch before the clock starts. Ask workers to save detailed results to their assigned paths and return a concise status, changed files, tests or citations, and any blocker. In Codex, use the host's subagent tools when available. For this workflow in T3 Code, use app-provided `delegate_task` and `task_status` when exposed. If that path is unavailable, keep the work in the parent and run it between games. Retain the worker handle and check the same task after a status timeout. Leave Codex worker model and effort at host defaults. The frozen cohort settings apply to the player.

```text
Task: Check the evaluator's timeout handling with an offline synthetic fixture.
Base: <commit>. Worktree: <path>. Writable paths: <files>.
Run the targeted test plus the repository checks. Report files, test results,
and blockers. Use synthetic data and shell tools only. Keep Git publishing
with the parent. The parent will review after the match.
```

Let independent jobs run in the background while the player moves. Defer research and test findings to between-game maintenance. Keep chess evaluations, suggested moves, and candidate rules out of the player context. If worker messages reach the live trace, record when they arrived and flag any effect on the player protocol or token attribution. Track worker usage separately wherever the host exposes it.

Verify the completed game's ledger, review, and archive before queueing again. Preserve interrupted attempts with the last verified state and any available platform result. The parent checks sanitized diffs and runs the repository checks before authorized PRs and merges. See the [capture, review, and verification commands](../README.md).
