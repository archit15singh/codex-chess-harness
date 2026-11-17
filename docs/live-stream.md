# Stream an authorized game on Twitch

Use OBS as a separate output. The player still reads the frozen native screenshots, clicks visible controls, and archives the full evidence locally. Record stream status, interruptions, and timing effects in the attempt notes.

1. In OBS, choose Twitch under **Settings → Stream**. If **Connect Account** crashes, open **Creator Dashboard → Settings → Stream** on Twitch and paste the primary stream key directly into the masked OBS field. Keep that key out of chat, shell history, screenshots, and Git. [Twitch stream-key guide](https://help.twitch.tv/s/article/twitch-stream-key-faq)
2. Create an empty standby scene and a gameplay scene. Use **macOS Screen Capture** in **Window Capture** mode with a dedicated Brave gameplay window. Crop to the board and mute every audio input. Verify the scene off-air. [OBS macOS capture guide](https://obsproject.com/kb/macos-screen-capture-source)
3. Start from standby. Confirm Twitch Stream Manager shows **Live** and the expected preview. Switch to gameplay only after the board is visible and the crop is verified. Return to standby before opening match history, results, or review files. If the window, zoom, or layout changes, return to standby and verify the crop before showing it again.
4. Finish the normal outcome and Elo readback, then review and archive offline before the next match. Stop streaming when gameplay ends. Verify Twitch returns to **Offline**.

Match introductions and history can contain identities inside the board's screen region. Keep standby active through transitions. A separate window and a crop constrain the scene while that window shows a game. The crop alone cannot hide a different view that opens in the same region.
