# Shortcuts

| Keys | Opens |
|---|---|
| `Super + Ctrl + Return` | Terminal running herdr |
| `Super + Alt + Return` | Terminal running tmux |
| `Super + Shift + /` | KeePassXC (focuses it if already open) |
| `Super + Shift + Alt + Return` | Browser in a private (incognito) window |

## Why they went missing

Omarchy only binds these keys while its preinstalled apps are kept. When the
preinstalls are removed, it creates `~/.local/state/omarchy/preinstalls-removed`,
and `o.preinstalled_bindings_enabled()` then skips the whole block in
`/usr/share/omarchy/default/hypr/bindings/applications.lua`. That block includes
tmux, herdr and the password manager.

The private browser key isn't one of those: Omarchy binds a private window to
`Super + Shift + Alt + B`, and this adds the same action next to
`Super + Shift + Return` (the browser), so both sit on the Return key.

## Install

```sh
./install.sh shortcuts
```

This installs `tmux`, `herdr` and `keepassxc` if they're missing, then adds the three
bindings to `~/.config/hypr/bindings.lua` (marked `sepro.shortcuts`, added once),
plus the private browser binding (marked `sepro.browser-private`).
Hyprland reloads on save. Check with:

```sh
hyprctl configerrors
omarchy menu keybindings --print | grep -E 'Tmux|Herdr|Passwords|private'
```

## KeePassXC

Passwords live in a local `.kdbx` file; there is no account or cloud. To use
them elsewhere, sync that file yourself (Syncthing, Nextcloud, ...) and open it
with KeePassDX (Android) or Strongbox (iOS). For autofill in Chrome, enable
*Browser Integration* in KeePassXC settings and install the KeePassXC-Browser
extension.

To use another password manager, change the last line in `bindings.lua`, e.g.
Omarchy's default: `o.bind("SUPER + SHIFT + SLASH", "Passwords", { omarchy = "1password" })`.
