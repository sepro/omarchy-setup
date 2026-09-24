---
name: track-changes
description: >
  Record every system change made in this session in ~/Git/omarchy-config so
  that running its install.sh on a fresh Omarchy install applies the same changes.
  Use ONLY when the user invokes /track-changes or explicitly asks to track changes
  in omarchy-config. Once active it stays active for the rest of the session and
  covers every later change (Hyprland, bar, themes, scripts, packages, /etc, services).
  Use it alongside the omarchy skill, which still decides how to make a change.
---

# track-changes

The repo `~/Git/omarchy-config` (`$REPO` below) holds sepro's Omarchy
customizations. Running `./install.sh` on a fresh Omarchy install must reproduce
this machine. While this skill is active, **no change to the system is finished
until the repo can reproduce it.**

## Activation

- The skill turns on when the user types `/track-changes` or asks for it. It then
  **stays on for the rest of the session**, so every later change is tracked
  unless the user says "don't track this" or "stop tracking".
- Confirm in one line that tracking is on. Don't check for drift at this point
  (see [Drift check](#drift-check-only-when-asked)).
- Use the `omarchy` skill for *how* to customize (Hyprland Lua, `omarchy bar`,
  themes, hooks). This skill covers *recording* the change.

## What to track

Track anything the requested change needs to work on a fresh install:

- User config and scripts: `~/.config/**` (hypr, omarchy, shell.json, plugins,
  themes, hooks, app configs), `~/.local/bin`, `~/.local/share/applications`,
  user systemd units, MIME defaults.
- Packages installed, and packages removed.
- System files (sudo): `/etc`, `/usr/share/plymouth`, system services, initramfs, boot.
- Steps that can't be scripted (browser extensions, logins, GUI-only settings):
  document these as manual steps.

Never edit `/usr/share/omarchy`. `omarchy update` overwrites it. Override from
`~/.config` instead, the way the omarchy skill describes.

## Workflow: repo first, then deploy

For each change:

1. **Understand** what the change needs. Read `$REPO/README.md` and
   `install.sh` (`--list`) to see whether an existing component already covers it.
2. **Pick the component** (see [Choosing a component](#choosing-a-component)).
3. **Write the files in the repo**, not in `~/.config`:
   - Put files in the component's folder (`$REPO/<component>/…`, or
     `$REPO/plugins/sepro.<name>/` for shell plugins).
   - Add or extend `do_<component>()` in `install.sh` (see
     [install.sh conventions](#installsh-conventions)).
4. **Deploy with the installer**: `bash -n install.sh && ./install.sh <component>`.
   Don't copy files by hand, and don't edit the live file directly. If the
   installer can't apply the change, fix the installer.
   - If a step needs sudo, tell the user it will prompt, or ask them to run
     `! ./install.sh <component>` themselves.
5. **Check it works** on the live system (e.g. `hyprctl configerrors`,
   `omarchy menu keybindings --print`, restart the widget, look at the result).
   One install run is enough; no second idempotency run is needed.
6. **Document it** (see [Documentation](#documentation)), including a
   screenshot if the change is visual (see [Screenshots](#screenshots)).
7. **Ask before committing**: show `git status --short` and a short diff summary,
   and propose a commit message. Commit only when the user says yes. Never push.

If you had to experiment on the live system first (e.g. trying out values),
that's fine. Before calling the change done, move the final result into the repo
and redeploy it with `./install.sh <component>`, so the live state comes from
the repo.

### Undoing and changing

- A tracked change that is changed later gets updated in the repo too (files,
  install step, docs).
- If the user reverts something, remove it from the repo. If a fresh install
  would still need a cleanup step (e.g. undoing a line an older version
  appended), add that step to the component.
- If the user removes a package, add `omarchy pkg drop <pkg>` to the right
  component and explain why in a comment.

## Choosing a component

- **An existing component fits** (same feature, or same kind of thing, e.g. a
  new keybinding goes in `shortcuts`): extend it.
- **A real feature** (a widget, a service, a theme, an app integration): create
  a new component with its own folder, `do_` function and `docs/<component>.md`.
- **A small tweak that fits nowhere** (a single Hyprland setting, one app option):
  put it in a catch-all `tweaks` component. Create it the first time it's
  needed, with a `docs/tweaks.md` that gets one `##` section per tweak.
- If the choice isn't obvious, ask.

Component names are short kebab-case (`desktop-stats`, `herdr-scratchpad`).
Shell plugins use the `sepro.<name>` id.

## install.sh conventions

Follow the existing file. Reuse its helpers instead of writing new logic:

| Helper | Use |
|---|---|
| `install_file <src> <dest>` | Copy a file, backing up a differing existing one to `.bak-$STAMP` |
| `append_once <file> <marker> <text>` | Append a block (e.g. to `hypr/bindings.lua`, `autostart.lua`) only if `marker` is absent |
| `need_pkgs <pkgs…>` | Install missing packages with `omarchy pkg add` |
| `step` / `say` / `warn` | Output: component header / info / warning |

Patterns already in the file:
- **Templates with paths**: store `@HOME@` placeholders and render with
  `sed "s#@HOME@#$HOME#g"` into a temporary `.new` file, `install_file` it, then
  remove the temporary file (see `do_vlc`, `do_torrents`).
- **Theme-driven files**: `.tpl` files go in `~/.config/omarchy/themed/`, and
  theme-set hooks are installed with `omarchy hook install theme-set <file>`.
- **Bar widgets**: check `shell.json` first, then use `omarchy bar put … --after …`
  with a `--section` fallback and a `warn` with the manual command.
- **Hyprland lines**: `append_once` with a unique marker (`sepro.<name>` or the
  script name) and a `--` comment explaining why.
- **JSON edits** (`shell.json`): use `jq`, back up to `.bak-$STAMP` first, and
  make the check idempotent.
- **User services**: `install_file` the unit to `~/.config/systemd/user/`,
  run `daemon-reload`, then `enable --now`.
- **System files**: `sudo install …` and explain the need for sudo in `step`
  (see `do_plymouth`).
- **Live-session actions** (reload, restart a process) are guarded by
  `[[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]`.
- **Unscriptable steps**: print them with `say` in the component as well as
  documenting them.

When adding a component, update **all** of:
1. `ALL=(…)` array
2. the header comment's component list
3. the `case` dispatch in main
4. the theme re-apply condition at the bottom, if the component ships `.tpl` files

The installer must stay idempotent: it can run again at any time without
duplicating lines or breaking an existing setup.

## Machine-specific values and secrets

- Put values specific to this machine or to the user (location, disk mounts,
  share paths, hostnames, usernames) in **clearly named variables at the top** of
  the script or config that uses them. Mention them in the doc's Install section
  and, if they need checking, in `say` output.
- **Never commit secrets**: no passwords, API tokens, keys, VPN credentials or
  cookies. Read them at runtime from an untracked file or the keyring, or
  document entering them as a manual step. Before proposing a commit, check the
  diff for anything that looks like a secret.
- Add generated or local-only files to `.gitignore`.

## Documentation

Match the existing docs (read one or two in `docs/` first):

- **`docs/<component>.md`**: a `#` title with a short description; what it does
  and why; `## Install` with `./install.sh <component>` and what it
  changes/where; `## Usage` (table of keys/actions) where relevant; how it works or
  troubleshooting when useful. For `tweaks`, add a section to `docs/tweaks.md`.
- **README.md**:
  - add a row to the Features table (emoji, **bold name**: one-line
    description, link to the doc)
  - add the component to the `Components:` list
  - add any manual step to the manual steps list
- **Screenshots**: required for visual changes (see [Screenshots](#screenshots)).
- Write in the same plain, direct style: explain the non-obvious reason behind
  a workaround.

## Screenshots

If a change adds or changes something **visible** (a widget, a popup, a theme,
the bar, a boot or lock screen, how an app looks), a screenshot of the finished
change is part of it. Take it yourself; don't leave it as a reminder.

1. **Bring the change on screen**, e.g. `omarchy-shell sepro.<name> toggle`,
   launch the app, or `omarchy theme set …`. Wait a moment for it to render.
2. **Capture only the part that matters**, using `grim` so nothing interactive
   opens:
   - A window: get its geometry from `hyprctl activewindow -j` or `hyprctl clients -j`
     (`at`, `size`), then run `grim -g "X,Y WxH" <file>`.
   - A popup or panel (layer surface): get its geometry from `hyprctl layers -j`.
   - The whole desktop: `grim <file>`, but use a region when the change is small.
   - If it can only be shown by hovering, clicking or starting up (tooltips,
     menus, Plymouth, lock screen), ask the user to set up the screen and run
     `omarchy capture screenshot region save` (or `fullscreen save`), then
     use the path it prints.
3. **Look at the image** with the Read tool before adding it. Check that it shows
   the change, and that nothing private is on screen (notifications, file
   names, messages, emails, tokens). Retake it if needed.
4. **Save it** as `docs/img/<component>.jpg` (or `-<detail>` for extra images).
   Use `.png` for small UI crops; for large or photographic ones, use
   `magick in.png -resize '1920x1920>' -quality 85 out.jpg` to keep it under
   ~600 KB.
5. **Embed it** in `docs/<component>.md` right after the intro paragraph:
   `![Short alt text](img/<component>.jpg)`. For tweaks, embed it under the
   tweak's section. If the change alters the overall look of the desktop,
   offer to retake `docs/img/desktop.jpg` for the README too.
6. When a later change makes an existing screenshot outdated, retake it.

Only skip the screenshot if the user says so; note that in the doc.

## Drift check (only when asked)

Only when the user asks ("check drift", "is everything tracked?"): for each
component, compare what `install.sh` would install with the live files (`cmp`/
`diff` the repo sources against their destinations, render templates first,
grep for `append_once` markers), and check `pacman -Qe` for explicitly installed
packages no component mentions. Report differences and offer to track or revert
each one. Don't change anything without asking.

## Before calling a change done

- [ ] Files live in the repo; the live system was updated with `./install.sh <component>`
- [ ] `bash -n install.sh` passes; the change works on the live system
- [ ] New component: added to `ALL`, header comment, `case` dispatch
- [ ] Doc page/section written; README features row + components list updated
- [ ] Visual change: screenshot taken, checked, saved in `docs/img/`, embedded in the doc
- [ ] No secrets in the diff; machine-specific values are variables
- [ ] Asked the user before committing (message style: `Add <thing>: <what it does>`)
