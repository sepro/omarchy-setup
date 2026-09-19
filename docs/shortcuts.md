# Shortcuts

| Keys | Opens |
|---|---|
| `Super + Ctrl + Return` | Terminal running herdr |
| `Super + Alt + Return` | Terminal running tmux |
| `Super + Shift + /` | KeePassXC (focuses it if already open) |

## Why they went missing

Omarchy only binds these keys while its preinstalled apps are kept. When the
preinstalls are removed, it creates `~/.local/state/omarchy/preinstalls-removed`,
and `o.preinstalled_bindings_enabled()` then skips the whole block in
`/usr/share/omarchy/default/hypr/bindings/applications.lua`. That block includes
tmux, herdr and the password manager.

## Install

```sh
./install.sh shortcuts
```

This installs `tmux`, `herdr` and `keepassxc` if they're missing, then adds the three
bindings to `~/.config/hypr/bindings.lua` (marked `sepro.shortcuts`, added once).
Hyprland reloads on save. Check with:

```sh
hyprctl configerrors
omarchy menu keybindings --print | grep -E 'Tmux|Herdr|Passwords'
```

## KeePassXC

Passwords live in a local `.kdbx` file; there is no account or cloud. To use
them elsewhere, sync that file yourself (Syncthing, Nextcloud, ...) and open it
with KeePassDX (Android) or Strongbox (iOS). For autofill in Chrome, enable
*Browser Integration* in KeePassXC settings and install the KeePassXC-Browser
extension.

To use another password manager, change the last line in `bindings.lua`, e.g.
Omarchy's default: `o.bind("SUPER + SHIFT + SLASH", "Passwords", { omarchy = "1password" })`.
