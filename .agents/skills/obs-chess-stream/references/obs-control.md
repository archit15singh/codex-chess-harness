# OBS automation options

OBS documents built-in **obs-websocket v5** as its official remote-control interface starting in OBS 28. No OBS Project-maintained MCP server was found in the official remote-control guide or project sources searched. The protocol exposes scene inventory, window-source properties, crop transforms, mute status and stream status and control. [OBS Remote Control Guide](https://obsproject.com/kb/remote-control-guide) · [OBS WebSocket protocol](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md)

| Option | Fit |
| --- | --- |
| Direct WebSocket | The harness uses a Node client with a fixed command list, authenticated access and verified scene changes. The client connects to loopback. OBS 33 may listen on all interfaces, so verify the listener and keep authentication enabled. [OBS listener implementation](https://github.com/obsproject/obs-websocket/blob/master/src/websocketserver/WebSocketServer.cpp) |
| Tom-R-Main OBS-MCP | Community MCP with macOS window selection, crop transforms, previews, tool filtering and optional live confirmations. The project documents a bounded macOS test. This harness has not installed or tested it. [Repository](https://github.com/Tom-R-Main/OBS-MCP) |
| aaronckj obs-studio-mcp | Community Python MCP with scene switching, mute, screenshots and stream controls. The documented tool list omits capture-source creation and crop transforms. [Repository](https://github.com/aaronckj/obs-studio-mcp) |
| obs-cmd | Community CLI with released binaries and documented scene, crop, mute and streaming operations. [Command coverage](https://github.com/grigio/obs-cmd/blob/master/OBS_WEBSOCKET_V5_STATUS.md) |
| OBS Lua or Python scripts | Official in-process alternative for local hotkeys or scene logic. Scripts run inside OBS. [OBS scripting docs](https://docs.obsproject.com/scripting) |

The OBS WebSocket password authenticates the control connection. The Twitch stream key stays in the OBS profile. A generic operator can expose it through stream-service settings. The harness client excludes that request and emits only specific status fields. [OBS request implementation](https://github.com/obsproject/obs-websocket/blob/master/src/requesthandler/RequestHandler_Config.cpp)

A working WebSocket connection verifies control of OBS. macOS must still grant capture access, the designated source must render, and Twitch Stream Manager must verify delivery. OBS 33.0.1 can crash in the Google sign-in path on macOS when the application lacks a Bluetooth usage description. Use Twitch's stream-key flow when that crash occurs. [OBS issue #14125](https://github.com/obsproject/obs-studio/issues/14125)
