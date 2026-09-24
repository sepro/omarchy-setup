# Claude Code skills

Claude Code skills that are kept in this repo and symlinked into
`~/.claude/skills`, so they come back on a fresh install and edits to them
end up in git straight away.

## Install

```sh
./install.sh claude-skills
```

This links every folder in `claude/skills/` to `~/.claude/skills/<name>`. If a
file or folder with that name already exists, it is moved aside to
`<name>.bak-<timestamp>` first. Omarchy's own skills (`omarchy`,
`diagnose-crash`) are separate symlinks into `/usr/share/omarchy` and are left
alone.

## track-changes

Type `/track-changes` in Claude Code to have every change made in that session
recorded in this repo, so `./install.sh` can apply it again on a new Omarchy
install. It stays on until the session ends, or until you say "stop tracking".
It works alongside the `omarchy` skill: that skill decides *how* to make a
change, and this one makes sure the change gets recorded.

For each change, Claude:

1. writes the files in the repo and the `do_<component>` step in `install.sh`
   (extending an existing component, a new one for a real feature, or `tweaks`
   for small one-offs),
2. applies it to the live system by running `./install.sh <component>`, and
   checks it works,
3. writes `docs/<component>.md` plus the README row and components list,
4. takes a screenshot of visual changes, checks it, and adds it to `docs/img/`
   and the doc,
5. shows the diff and asks before committing (it never pushes).

It covers user config, packages (installs and removals), system files under
`/etc` and similar, and documents steps that can't be scripted. Values specific
to this machine go into variables at the top of the file that uses them, and
secrets are never committed.

Ask "check drift" to compare the live system with what the repo would
install.

The instructions are in
[`claude/skills/track-changes/SKILL.md`](../claude/skills/track-changes/SKILL.md).
