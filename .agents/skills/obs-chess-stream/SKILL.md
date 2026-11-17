---
name: obs-chess-stream
description: Set up, verify, and operate a board-only Twitch broadcast of an authorized Codex chess session from Brave using OBS Studio. Use for requests to stream live chess, troubleshoot OBS capture, or switch between board and standby during play.
---

Run commands from the harness root with `node .agents/skills/obs-chess-stream/scripts/obs.mjs` followed by the subcommand. Use OBS WebSocket v5 with authentication and a local client. Keep Twitch authentication in the OBS profile. Read the [streaming runbook](../../../docs/live-stream.md) for manual setup and the [integration research](references/obs-control.md) when evaluating an MCP or another driver.

1. Run `status`. With output offline, open chess in a dedicated Brave window. Run `windows` to provision the two named scenes and enumerate Brave windows. Select the dedicated window with `prepare WINDOW_ID`. Switch to the empty `standby` scene. Run `mute` to silence the capture and global OBS audio.
2. Use `preview evidence/private/stream-preflight/<new-name>.png` with an existing private directory. Read its source dimensions and inspect the private image. During an authorized game, derive the four crop edges from the current native screenshot and OBS source dimensions. Run `crop LEFT TOP RIGHT BOTTOM` while on standby, then render and **visually verify** a fresh preview. OBS crop metadata alone cannot establish that the stream shows only the board.
3. Start the authorized broadcast with `start` from standby. Check Twitch Stream Manager in a separate Brave window. Run `board` only while the verified crop shows the settled game board. Confirm the actual program feed in Twitch and return focus to the dedicated Brave gameplay window. Keep chat and OBS previews outside move selection.
4. Run `standby` before any transition away from the board. Verify the platform outcome and Elo, then complete the offline engine review and archive before the next game. Record broadcast status and timing deviations in private attempt notes. Run `stop` when the broadcast ends and verify Twitch shows Offline. If a scene switch fails while live, use `stop` and verify output status before opening any identity-bearing page.

Use unique preview paths on every capture. Source previews may contain private material and belong in ignored evidence. Use the regular frozen gameplay controller for observations and moves.
