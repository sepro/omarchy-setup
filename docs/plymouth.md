# Koi Pond boot splash (Plymouth)

A Plymouth theme that shows the Koi Pond wallpaper with the Omarchy logo,
together with the stock Omarchy progress bar and disk-unlock password prompt.

![Plymouth splash](img/plymouth.jpg)

## Install

```sh
./install.sh plymouth     # needs sudo
```

It copies `plymouth/` to `/usr/share/plymouth/themes/koi-pond/`, runs
`plymouth-set-default-theme koi-pond` and rebuilds the initramfs
(`limine-mkinitcpio` on Omarchy, `mkinitcpio -P` elsewhere). Reboot to see it.

## Files

| File | Role |
|---|---|
| `koi-pond.plymouth` | Theme descriptor (script module, `#121212` console) |
| `koi-pond.script` | Scales `background.png` to cover the screen, then draws the progress bar and password prompt |
| `background.png` | 1920×1080 wallpaper with the white logo baked in (800×188, centred) |
| `lock.png`, `entry.png`, `bullet.png`, `progress_*.png` | Omarchy's stock prompt and progress assets |

Preview without rebooting (needs sudo):

```sh
sudo plymouthd; sudo plymouth --show-splash; sleep 5; sudo plymouth quit
```

To revert: `sudo plymouth-set-default-theme omarchy && sudo limine-mkinitcpio`.
