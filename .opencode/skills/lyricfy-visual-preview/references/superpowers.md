# Superpowers Visual Companion

`../vendor/superpowers/` contains the unmodified `server.cjs`,
`frame-template.html`, `helper.js`, and MIT license from
[obra/superpowers v7.0.2](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/brainstorming/scripts)
(commit `22f0b463e7a5e579904dd6211a520321035526f7`). Only the browser preview
runtime is bundled, not the OpenCode plugin or the other Superpowers skills.
Updates should use a reviewed, fixed upstream commit and retain its license.

See the upstream [Visual Companion guide](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/brainstorming/visual-companion.md)
for the preview protocol. Lyricfy's Node launcher replaces the Bash launcher so
PowerShell works without Git Bash or WSL. It uses loopback only, a fresh keyed
session, and local files. Upstream telemetry and automatic opening of browser
tabs are disabled.
