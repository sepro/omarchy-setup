# Lock screen: reclaim focus after suspend/resume

After resuming from suspend, Omarchy's lock screen password field didn't
accept typing until it was clicked once. `LockView.qml`'s password `TextInput`
only requests keyboard focus when the lock view is first created or when
`inputEnabled` toggles. Omarchy's sleep helper locks the session *before*
suspending and waits for it to become secure, so that focus request happens
well before the suspend/resume transition — and nothing re-requests it once
the display comes back.

This is a `sepro.lock` clone of the built-in `omarchy.lock` plugin
(`omarchy plugin clone omarchy.lock`) with one addition to `Service.qml`: it
watches logind's `PrepareForSleep` D-Bus signal for the resume edge
(`boolean false`) and calls the existing `forcePasswordFocus()` on the lock
view again, after a short delay to let the session-lock surface come back.

## Install

```sh
./install.sh lockfix
```

Installs `plugins/sepro.lock/` to `~/.config/omarchy/plugins/sepro.lock/` and
enables it in `shell.json`, disabling the built-in `omarchy.lock` the same way
`omarchy plugin clone` does. Being a user plugin, it survives `omarchy
update`; if Omarchy's own lock plugin changes, re-diff
`/usr/share/omarchy/shell/plugins/lock/` against this clone and re-apply the
`PrepareForSleep` addition.

## How it works

`Service.qml` gains:
- a `Process` running `dbus-monitor` filtered to
  `org.freedesktop.login1.Manager.PrepareForSleep`, matching the same signal
  Omarchy's own `omarchy-system-sleep-monitor` listens for before suspend.
- on the `boolean false` (resume) line, a 300 ms timer calls
  `lockView.forcePasswordFocus()`, reusing the function the view already calls
  on its own creation.
