---
name: openclaw
description: >
  Inspect, troubleshoot and fix the OpenClaw instance (personal AI assistant
  gateway with a Telegram channel) running on the "openclaw" Debian box on the
  LAN, over SSH. Use when the user invokes /openclaw or asks to check, debug,
  update or change OpenClaw, its gateway, channels, agents, sessions, cron
  automations or config on that machine.
---

# openclaw

Work on the OpenClaw machine over SSH. The task comes from the user's
`/openclaw <assignment>` arguments; with no assignment, run the health check
below and report.

## Connecting

The host alias `openclaw` is in `~/.ssh/config` (it holds the IP, user and
key `~/.ssh/openclaw`; run `ssh -G openclaw | grep -E '^(hostname|user) '`
to see them, and never copy them into this repo). Always use non-interactive SSH, and put this PATH
first in every command. A non-interactive shell doesn't load it, so `openclaw`
and `node` are otherwise not found:

```sh
ssh -o BatchMode=yes -o ConnectTimeout=5 openclaw \
  'export PATH=$HOME/.openclaw/bin:$HOME/.openclaw/tools/node/bin:$PATH; <cmd>'
```

`tools/node` is a symlink to the current Node, so this PATH survives Node
updates.

If SSH fails, stop and report it. Ping the `HostName` from `ssh -G openclaw`
and check whether port 22 answers. The IP comes from DHCP and has changed before, so it may have moved
again (`avahi-browse -atrp`, or ask the user). Never try passwords or other
users.

## Layout (as found 2026-10-23)

- Debian 13 (trixie), 2 cores / 3.8 GB RAM / 30 GB disk, hostname `openclaw`.
- OpenClaw 2026.10.6 (updated 2026-10-23), installed via npm into `~/.openclaw`, with its own node
  in `~/.openclaw/tools/node-v24.22.1` (symlinked as `tools/node`); CLI at `~/.openclaw/bin/openclaw`.
- **Gateway**: process `openclaw-gateway`, listening on `127.0.0.1:18789` and
  `[::1]:18789` only (not reachable from the LAN; use SSH, or an SSH tunnel
  `ssh -L 18789:127.0.0.1:18789 openclaw` for the dashboard).
  Runs as the systemd **user** service `openclaw-gateway.service` (installed
  2026-10-23, `Restart=always`); under systemd the process shows as `node`, so
  use `systemctl --user status openclaw-gateway` and
  `journalctl --user -u openclaw-gateway`, not `pgrep`. Restart with
  `systemctl --user restart openclaw-gateway` (takes ~15 s to listen). If
  `Linger=no` (`loginctl show-user $USER -p Linger`), it won't start after a
  reboot until someone logs in; the fix is `sudo loginctl enable-linger $USER`
  (user runs it).
- Heartbeat is deliberately off (`agents.defaults.heartbeat.every = "0m"`).
  Memory search is deliberately keyword-only (`memory.search.provider =
  "none"`). The user doesn't want local/embedding models installed. Cron
  jobs failing with credit/billing errors mean the Anthropic credit is empty;
  that's the user's to top up, not a bug.
- Config: `~/.openclaw/openclaw.json` (mode 600). OpenClaw keeps rotating
  backups next to it (`.bak`, `.bak.1`–`.4`, `.last-good`).
- State: `~/.openclaw/agents/main/agent/openclaw-agent.sqlite` (sessions),
  `workspace/`, `memory/`, `cron/`, `credentials/`, `telegram/`, `logs/`
  (stability reports such as `*.startup_failed.json`).
- Gateway log: `/tmp/openclaw/openclaw-YYYY-MM-DD.log` (JSON lines, one file
  per day; it lives in /tmp and is gone after a reboot).
- One agent (`main`), default model claude-sonnet-5-5; Telegram is the only
  channel. Several cron automations run as `agent:main:cron:*` sessions.
- `sudo` needs a password, so system-level changes (apt, /etc, system units)
  are not possible non-interactively. Hand those to the user as commands to
  run in a real terminal (`ssh -t openclaw` then the command).

- No `jq` on the box; read config with `openclaw config get <key>`.
- `openclaw backup create` fails on this install (`whisper-venv` has absolute
  symlinks). Back up with tar instead, into `~/openclaw-backups/`:
  `tar czf ~/openclaw-backups/openclaw-state-$(date +%Y%m%d-%H%M%S).tar.gz -C ~ --exclude=.openclaw/tools --exclude=.openclaw/whisper-venv --exclude=.openclaw/cache .openclaw`

## Updating

It's a user-space install (made by `install-cli.sh`), so when a release
raises the Node floor, `openclaw update` refuses. Then update both together,
without sudo, using the user-space installer (download it, read it, then run):

```sh
curl -fsSL https://openclaw.ai/install-cli.sh -o /tmp/openclaw-install-cli.sh
bash /tmp/openclaw-install-cli.sh --prefix "$HOME/.openclaw" --version <ver> --no-onboard
```

Not `install.sh`: that one may install a system Node with sudo. Read the
GitHub release notes for every version in between first
(`gh api repos/openclaw/openclaw/releases/tags/vX`) and look for "Breaking"
lines. The old gateway keeps running the old code until restarted.

After installing (as done for 2026.9.2 -> 2026.10.6):

1. `openclaw doctor --lint`. Pending state or agent schema migrations need
   the gateway **stopped** first (`systemctl --user stop openclaw-gateway`).
2. Copy the stopped `*.sqlite*` files into `~/openclaw-backups/`, then run
   `openclaw doctor --fix --non-interactive` (log it to a file).
3. Start it again: `systemctl --user start openclaw-gateway`, then check
   `openclaw status` (Gateway self version, Telegram OK).

If npm fails with a missing file inside a dependency (for example `koffi`
`cnoke.cjs` MODULE_NOT_FOUND) and the npm log says a tarball "seems to be
corrupted", the npm cache is bad: run `npm cache clean --force` and run the
installer again. A failed install leaves the old version runnable.

Re-check this section when something doesn't match. If the layout has
changed, update this file and tell the user.

## Health check

Read-only; run without asking:

```sh
openclaw --version
openclaw status            # overview, channels, sessions; --deep for probes
openclaw doctor --help     # check flags first; only run its fix mode with approval
openclaw cron --help       # then list automations and recent runs
systemctl --user status openclaw-gateway --no-pager | head -5; ss -tln | grep 18789
grep -E '"(level|logLevelName)":"?(error|warn|ERROR|WARN)' /tmp/openclaw/openclaw-$(date +%F).log | tail -20
ls -lt ~/.openclaw/logs | head
uptime; df -h /; free -h
```

Things to report on: is the gateway up and reachable, Telegram channel
state, failed or stuck cron runs / "Tasks … issues", the heartbeat warning,
errors in today's log, low disk/memory, available updates
(`openclaw update --help` to see how to check), and recent stability reports.

Use `openclaw <command> --help` and `openclaw docs <query>` to look up the
CLI rather than guessing flags. The CLI changes between versions.

## Rules for changes

1. **Look first, then report**: say what you found and what you propose
   before changing anything.
2. **Ask before** restarting the gateway, editing config, updating OpenClaw,
   changing cron automations, deleting sessions/state, or anything touching
   credentials. Read-only commands need no approval.
3. Prefer the CLI (`openclaw config get/set/patch/validate`) over editing
   `openclaw.json` by hand. If you must edit it, copy it first to
   `openclaw.json.claude-<timestamp>` and run `openclaw config validate` after.
4. **Restarting the gateway**: `systemctl --user restart openclaw-gateway`.
   Confirm afterwards with `openclaw status` that it's reachable and Telegram
   is OK. Never start a second gateway by hand next to the service; it
   refuses to start while another one owns the state directory.
5. **Never print secrets**: don't cat `openclaw.json`, `credentials/`,
   `identity/` or tokens into the conversation. Use
   `openclaw config get <key>` for specific non-secret keys, or `jq` with
   secret-looking fields removed.
6. Don't write anything into the user's workspace, memory or sessions unless
   the task is about them.
7. Finish with a short summary: what was wrong, what you changed (with file
   paths and backup names), what's left for the user.
