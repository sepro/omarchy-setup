# Lock screen: reclaim focus after suspend/resume

After resuming from suspend, Omarchy's lock screen password field didn't
accept typing until it was clicked once. Locking without suspending was fine.
Suspend takes keyboard focus off the field (the lock window is deactivated as
the machine goes down), and the field only requests focus when the lock view
is created or when `inputEnabled` toggles, both of which happen before suspend.
Nothing asked for focus again after resume.

This is a `sepro.lock` clone of the built-in `omarchy.lock` plugin
(`omarchy plugin clone omarchy.lock`) that re-takes focus the moment logind
reports resume.

## Install

```sh
./install.sh lockfix
```

Installs `plugins/sepro.lock/` to `~/.config/omarchy/plugins/sepro.lock/` and
enables it in `shell.json`, disabling the built-in `omarchy.lock` the same way
`omarchy plugin clone` does. When the plugin files changed, the installer
restarts the shell (`omarchy restart shell`): the shell's hot reload says it
reloaded the plugin but keeps the old lock service running.

Being a user plugin, it survives `omarchy update`, but it also stops picking up
Omarchy's own lock fixes. After an update that touches
`/usr/share/omarchy/shell/plugins/lock/`, re-copy `LockView.qml` and
`Service.qml` from there and re-apply the additions below (search for
`resumeSerial`).

## How it works

- `Service.qml` runs `dbus-monitor` on logind's `PrepareForSleep` signal (the
  same one Omarchy's `omarchy-system-sleep-monitor` locks on) and, on the
  resume edge (`boolean false`), bumps a `resumeSerial` counter.
- The lock view is a per-screen `WlSessionLockSurface` delegate, so the service
  can't call into it by id (an earlier version tried and failed with
  `ReferenceError: lockView is not defined`). Each `LockView` instead takes
  `resumeSerial` as a property and, when it changes, calls its own
  `forcePasswordFocus()` immediately, then re-checks every 150 ms for 2 s in
  case the first request lands too early.

## Known limitation: a short wait while the keyboard wakes

Keystrokes typed in the first ~0.5 s after resume are lost: the laptop
keyboard is reinitialised a little after the lock screen is back (the moment
the Num Lock LED lights up again). That's kernel/hardware timing the lock
screen can't shorten.

A "Waking keyboard…" hint was tried and dropped. Right after resume Hyprland
keeps showing the lock surface's last frame until input wakes the display, so
the hint never cleared on its own, and forcing a redraw blanked the panel for
a moment, which was worse than the wait.
