'use strict';

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const skillDir = path.resolve(__dirname, '..');
const repoDir = path.resolve(skillDir, '../../..');

function start() {
  if (process.argv.length > 3) throw new Error('Usage: node start-preview.cjs [screen.html]');
  if (Number(process.versions.node.split('.')[0]) < 20) throw new Error('Visual Preview requires Node.js 20 or newer.');

  const customScreen = process.argv[2];
  const screen = customScreen ? path.resolve(customScreen) : path.join(skillDir, 'mockups', 'taskbar-left-pause.html');
  const basename = path.basename(screen);
  if (basename.startsWith('.') || !basename.endsWith('.html') || !fs.statSync(screen).isFile()) {
    throw new Error('Choose an existing, visible .html file.');
  }

  const sessions = path.join(repoDir, '.superpowers', 'brainstorm');
  fs.mkdirSync(sessions, { recursive: true });
  const session = fs.mkdtempSync(path.join(sessions, 'lyricfy-'));
  const content = path.join(session, 'content');
  fs.mkdirSync(content);
  fs.copyFileSync(screen, path.join(content, basename));
  if (!customScreen) {
    fs.copyFileSync(path.join(repoDir, 'assets', 'screenshots', 'taskbar-left.png'), path.join(content, 'taskbar-left.png'));
  }

  // Do not inherit upstream settings that could change the bind address,
  // reuse a session key, or run a browser launcher command.
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !/^BRAINSTORM_/i.test(key)));
  Object.assign(env, {
    BRAINSTORM_DIR: session,
    BRAINSTORM_HOST: '127.0.0.1',
    BRAINSTORM_URL_HOST: '127.0.0.1',
    BRAINSTORM_OWNER_PID: String(process.pid),
    SUPERPOWERS_DISABLE_TELEMETRY: '1',
  });
  const server = spawn(process.execPath, [path.join(skillDir, 'vendor', 'superpowers', 'server.cjs')], { env, stdio: 'inherit' });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.kill(signal));
  server.on('error', (error) => { console.error(error.message); process.exitCode = 1; });
  server.on('exit', (code, signal) => { process.exitCode = code ?? (signal === 'SIGINT' ? 0 : 1); });
}

try {
  start();
} catch (error) {
  console.error(`Visual Preview: ${error.message}`);
  process.exitCode = 1;
}
