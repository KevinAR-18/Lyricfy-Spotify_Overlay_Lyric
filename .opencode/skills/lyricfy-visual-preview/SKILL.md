---
name: Lyricfy Visual Preview
description: Compare proposed Lyricfy overlay layouts, styles, or playback states in an interactive localhost browser before editing the PySide6 app.
---

# Lyricfy Visual Preview

Use the browser when appearance or placement needs a decision. For behavior or scope questions that do not need a visual, use the conversation instead. Do not install a global plugin, start Spotify or Qt, or modify app code for visual review.

1. Read the relevant overlay code and look at an existing screenshot to match the real layout. Show a current-state comparison and only a few meaningful alternatives. Include the state or size that is most likely to expose a problem.
2. Once the user wants a browser review, run `node .opencode/skills/lyricfy-visual-preview/scripts/start-preview.cjs` from the repository root. Keep the process in a background tool task or a persistent terminal. The default screen is the Taskbar Left pause review. Pass a path to a different `.html` file as the sole argument to start a new session with that screen instead. Use Node.js 20 or later.
3. Use the `server-started` JSON printed by the server to find `url`, `screen_dir`, and `state_dir`. Verify the keyed localhost URL is reachable before sharing it. Never strip its `?key=…` or publish it outside the current review. Open the user's browser only if requested.
4. Ask the user to try the controls, select an option, and confirm in the conversation. Elements with `data-choice` record clicks in `state_dir/events`; read the last relevant choice if the user asks or reports having voted. A click is feedback, not approval to edit the app. For a revision, write a new uniquely named `.html` in `screen_dir` so open tabs reload. Copy any local assets the mockup needs into that same directory and reference them with `/files/<filename>`.
5. Stop the preview when review is over (`Ctrl+C` in its terminal or stop only the launched task). Session files under `.superpowers/brainstorm/` are local and ignored. Wait for the user to confirm the design before changing production files. Browser mockups do not validate native Windows taskbar coordinates, font metrics, or behavior.

The bundled companion is [Superpowers Visual Companion](references/superpowers.md). It serves only on `127.0.0.1`; the launcher disables upstream telemetry and automatic browser launch.
