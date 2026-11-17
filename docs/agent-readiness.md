# Agent readiness

A contributor should be able to find the right entry point, run the checks from a clean clone, and understand which work needs a signed-in browser. The root [AGENTS.md](../AGENTS.md) routes by task. The [README](../README.md) holds the commands, and tests hold executable examples of expected behavior. This applies the short repository map and progressive disclosure described by OpenAI. [Codex repository instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md) · [OpenAI harness engineering](https://openai.com/index/harness-engineering/)

The [checks workflow](../.github/workflows/checks.yml) runs the same Node and Python tests described in the README using a clean checkout with read-only repository access. It also rejects tracked files under `evidence/`. The tests exercise simulated controller I/O, PGN validation, engine lifecycle and archive behavior. [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)

A contributor can verify offline changes with no Duolingo account, browser session, Stockfish binary, or private archive. Live game outcomes and screenshot interpretation require the separate evidence described in the README. Use synthetic examples in public issues, tests and pull requests.
