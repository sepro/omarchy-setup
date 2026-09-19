# herdr keybindings

Omarchy ships a herdr config (`/usr/share/omarchy/config/herdr/config.toml`)
that remaps most keys to mimic its tmux setup: `Prefix + h` splits down,
`Ctrl + Alt + Arrows` move between panes, `Prefix + k` closes a tab, and so on.

This repo's [`herdr/config.toml`](../herdr/config.toml) keeps Omarchy's look
(terminal palette, no gaps or scrollbars, hostname in the tab bar) but drops
every key override except the prefix:

```toml
[keys]
prefix = "ctrl+space"
```

All other bindings are herdr's own defaults, so they match the
[cheat sheets](../cheat_sheets/) and the SUPER+CTRL+K keybindings menu. The
full list is in `herdr --default-config` and at https://herdr.dev/docs/keyboard.

## Install

```sh
./install.sh herdr
```

This copies the config to `~/.config/herdr/config.toml` (backing up the old one)
and reloads the running herdr server.

`omarchy-refresh-herdr` restores Omarchy's tmux-style config. Run
`./install.sh herdr` again afterwards to get the defaults back.
