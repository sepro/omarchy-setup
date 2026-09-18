#!/usr/bin/env bash
#
# Deploy sepro's Omarchy customizations onto a fresh Omarchy install.
#
#   ./install.sh                 install everything
#   ./install.sh theme vlc       install only the named components
#   ./install.sh --list          list components
#
# Components: theme, vlc, chrome, vlc-recent, desktop-stats, plymouth, jellyfin,
#             herdr-scratchpad, surfshark
#
# Idempotent: anything it would overwrite is backed up to <file>.bak-<stamp>,
# and lines appended to Hyprland config are only added once. Nothing under
# /usr/share/omarchy is touched, so `omarchy update` won't undo it.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%s)"
CFG="$HOME/.config"
ALL=(theme vlc chrome vlc-recent desktop-stats plymouth jellyfin herdr-scratchpad surfshark)

say()  { printf '  %s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }

# install <src> <dest>: copy a file, backing up a differing existing one.
install_file() {
  local src=$1 dest=$2
  mkdir -p "$(dirname "$dest")"
  if [[ -e $dest ]] && ! cmp -s "$src" "$dest"; then
    cp -p "$dest" "$dest.bak-$STAMP"
    say "backed up $(basename "$dest") -> $(basename "$dest").bak-$STAMP"
  fi
  cp "$src" "$dest"
}

# append_once <file> <marker> <text>: append text unless marker already present.
append_once() {
  local file=$1 marker=$2 text=$3
  mkdir -p "$(dirname "$file")"
  if [[ -f $file ]] && grep -qF -- "$marker" "$file"; then
    say "$(basename "$file"): already configured"
  else
    [[ -f $file ]] && cp -p "$file" "$file.bak-$STAMP"
    printf '\n%s\n' "$text" >>"$file"
    say "$(basename "$file"): appended"
  fi
}

need_pkgs() {
  local missing=()
  for p in "$@"; do pacman -Q "$p" &>/dev/null || missing+=("$p"); done
  if (( ${#missing[@]} )); then
    say "installing: ${missing[*]}"
    omarchy pkg add "${missing[@]}" || warn "package install failed: ${missing[*]}"
  fi
}

# ── components ────────────────────────────────────────────────────────

do_theme() {
  step "Koi Pond theme"
  mkdir -p "$CFG/omarchy/themes"
  rm -rf "$CFG/omarchy/themes/koi-pond"
  cp -r "$REPO/themes/koi-pond" "$CFG/omarchy/themes/"
  say "copied to ~/.config/omarchy/themes/koi-pond"
}

do_vlc() {
  step "VLC theme (qt5ct palette generated from the Omarchy theme)"
  need_pkgs vlc qt5ct
  install_file "$REPO/vlc/qt5ct-colors.conf.tpl" "$CFG/omarchy/themed/qt5ct-colors.conf.tpl"
  mkdir -p "$CFG/qt5ct"
  sed "s#@HOME@#$HOME#g" "$REPO/vlc/qt5ct.conf" >"$CFG/qt5ct/qt5ct.conf.new"
  install_file "$CFG/qt5ct/qt5ct.conf.new" "$CFG/qt5ct/qt5ct.conf"; rm -f "$CFG/qt5ct/qt5ct.conf.new"
  install_file "$REPO/vlc/vlc.desktop" "$HOME/.local/share/applications/vlc.desktop"
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
}

do_chrome() {
  step "Chrome theme (extension generated from the Omarchy theme)"
  install_file "$REPO/chrome/manifest.json.tpl" "$CFG/omarchy/themed/manifest.json.tpl"
  append_once "$CFG/chrome-flags.conf" "WaylandFractionalScaleV1" \
"# Fractional scaling (e.g. 1.5x) leaves a see-through row between the toolbar and the page
--disable-features=WaylandFractionalScaleV1"
  # Omarchy's BrowserThemeColor policy locks Chrome's theme ("blocked by the
  # administrator"). Omarchy only writes into policy dirs that exist, so moving
  # Chrome's aside disables it for good; Chromium/Edge/Brave are untouched.
  local pol=/etc/opt/chrome/policies/managed
  if [[ -d $pol && ! -L $pol ]]; then
    say "disabling Omarchy's Chrome colour policy (needs sudo)"
    sudo mv "$pol" "$pol.omarchy-disabled" || warn "could not move $pol"
  fi
  say "One manual step: chrome://extensions -> Developer mode -> Load unpacked ->"
  say "  $HOME/.local/state/omarchy/current/theme   (hidden: Ctrl+L in the picker, then paste)"
  command -v wl-copy >/dev/null && printf '%s' "$HOME/.local/state/omarchy/current/theme" | wl-copy \
    && say "  path copied to the clipboard"
  say "(Chrome stable ignores --load-extension, so it can't be automated.)"
}

do_vlc_recent() {
  step "Recently watched (VLC) bar widget"
  local dest="$CFG/omarchy/plugins/sepro.vlc-recent"
  mkdir -p "$dest"
  for f in "$REPO"/plugins/sepro.vlc-recent/*; do install_file "$f" "$dest/$(basename "$f")"; done
  chmod +x "$dest/vlc-recent.py"
  if grep -q '"sepro.vlc-recent"' "$CFG/omarchy/shell.json" 2>/dev/null; then
    say "shell.json: widget already in the bar"
  else
    omarchy bar put sepro.vlc-recent --after omarchy.tray \
      || omarchy bar put sepro.vlc-recent --section right \
      || warn "could not add widget; run: omarchy bar put sepro.vlc-recent --section right"
  fi
  append_once "$CFG/hypr/bindings.lua" "sepro.vlc-recent" \
'-- Recently watched (VLC) popup: ~/.config/omarchy/plugins/sepro.vlc-recent
o.bind("SUPER + M", "Recently watched", "omarchy-shell sepro.vlc-recent toggle")'
}

do_desktop_stats() {
  step "Desktop stats panel"
  need_pkgs python-gobject python-cairo gtk4-layer-shell
  for f in desktop-stats.py desktop-stats-restart.sh; do
    install_file "$REPO/desktop-stats/$f" "$CFG/hypr/scripts/$f"
    chmod +x "$CFG/hypr/scripts/$f"
  done
  append_once "$CFG/hypr/autostart.lua" "desktop-stats.py" \
'-- Desktop stats panel: a click-through GTK4 layer-shell surface on the
-- BACKGROUND layer (clock, CPU, RAM, temps, disks) painted on the wallpaper.
-- Restart after editing with ~/.config/hypr/scripts/desktop-stats-restart.sh
o.exec_on_start("python " .. os.getenv("HOME") .. "/.config/hypr/scripts/desktop-stats.py")'
  if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then
    "$CFG/hypr/scripts/desktop-stats-restart.sh"
    say "started (log: /tmp/desktop-stats.log)"
  fi
  say "Check DISKS at the top of desktop-stats.py matches this machine's mounts."
}

do_plymouth() {
  step "Koi Pond boot splash (Plymouth) — needs sudo"
  sudo install -d /usr/share/plymouth/themes/koi-pond
  sudo install -m644 "$REPO"/plymouth/* /usr/share/plymouth/themes/koi-pond/
  sudo plymouth-set-default-theme koi-pond
  say "rebuilding initramfs…"
  if command -v limine-mkinitcpio >/dev/null; then
    sudo limine-mkinitcpio
  else
    sudo mkinitcpio -P
  fi
}

do_jellyfin() {
  step "sync-jellyfin.sh"
  need_pkgs rsync
  install_file "$REPO/scripts/sync-jellyfin.sh" "$HOME/.local/bin/sync-jellyfin.sh"
  chmod +x "$HOME/.local/bin/sync-jellyfin.sh"
  say "installed to ~/.local/bin; try: sync-jellyfin.sh -n"
}

do_herdr_scratchpad() {
  step "herdr + Claude on the scratchpad (SUPER+S)"
  command -v herdr >/dev/null || warn "herdr not found; install it from https://herdr.dev"
  command -v claude >/dev/null || warn "claude not found on PATH"
  need_pkgs jq
  install_file "$REPO/herdr-scratchpad/herdr-scratchpad.sh" "$CFG/hypr/scripts/herdr-scratchpad.sh"
  chmod +x "$CFG/hypr/scripts/herdr-scratchpad.sh"
  append_once "$CFG/hypr/autostart.lua" "herdr-scratchpad" \
'-- herdr with Claude inside, parked on the scratchpad (SUPER+S shows it)
o.window("org.omarchy.herdr-scratchpad", { workspace = "special:scratchpad silent" })
o.exec_on_start(os.getenv("HOME") .. "/.config/hypr/scripts/herdr-scratchpad.sh")'
  if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then
    hyprctl reload >/dev/null
    setsid "$CFG/hypr/scripts/herdr-scratchpad.sh" >/dev/null 2>&1 &
    say "started; press SUPER+S"
  fi
}

do_surfshark() {
  step "Surfshark: pinned tray icon, no sticky Connected toast at login"
  install_file "$REPO/surfshark/surfshark-start.sh" "$CFG/hypr/scripts/surfshark-start.sh"
  chmod +x "$CFG/hypr/scripts/surfshark-start.sh"
  # Swap a plain launch_on_start("surfshark") for the wrapper.
  if grep -q 'o.launch_on_start("surfshark")' "$CFG/hypr/autostart.lua" 2>/dev/null; then
    cp -p "$CFG/hypr/autostart.lua" "$CFG/hypr/autostart.lua.bak-$STAMP"
    sed -i '/Surfshark VPN (shows up/d; /o.launch_on_start("surfshark")/d' "$CFG/hypr/autostart.lua"
  fi
  append_once "$CFG/hypr/autostart.lua" "surfshark-start.sh" \
'-- Surfshark VPN (tray icon pinned in shell.json); the wrapper dismisses its
-- never-expiring "Connected" toast after auto-connect
o.exec_on_start(os.getenv("HOME") .. "/.config/hypr/scripts/surfshark-start.sh")'
  # Surfshark is Electron, so its tray id is the generic chrome_status_icon_1.
  local sj="$CFG/omarchy/shell.json" id=chrome_status_icon_1
  if [[ -f $sj ]] && ! jq -e --arg id "$id" '.. | objects | select(.id == "omarchy.tray") | .pinned // [] | index($id)' "$sj" >/dev/null; then
    cp -p "$sj" "$sj.bak-$STAMP"
    jq --arg id "$id" '(.bar.layout[][] | select(.id == "omarchy.tray")) |= (.pinned = ((.pinned // []) + [$id]) | .hidden = ((.hidden // []) - [$id]))' \
      "$sj.bak-$STAMP" >"$sj"
    say "shell.json: pinned $id in the tray"
  else
    say "shell.json: tray icon already pinned"
  fi
}

# ── main ──────────────────────────────────────────────────────────────

case "${1:-}" in
  -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
  --list)    printf '%s\n' "${ALL[@]}"; exit 0 ;;
esac

command -v omarchy >/dev/null || { echo "This doesn't look like an Omarchy system." >&2; exit 1; }

COMPONENTS=("$@"); (( ${#COMPONENTS[@]} )) || COMPONENTS=("${ALL[@]}")
for c in "${COMPONENTS[@]}"; do
  case "$c" in
    theme) do_theme ;; vlc) do_vlc ;; chrome) do_chrome ;;
    vlc-recent) do_vlc_recent ;; desktop-stats) do_desktop_stats ;;
    plymouth) do_plymouth ;; jellyfin) do_jellyfin ;;
    herdr-scratchpad) do_herdr_scratchpad ;; surfshark) do_surfshark ;;
    *) warn "unknown component: $c (see --list)"; exit 2 ;;
  esac
done

# Apply the theme last so the VLC/Chrome templates get rendered by it.
if [[ " ${COMPONENTS[*]} " == *" theme "* ]]; then
  step "Applying theme"
  omarchy theme set koi-pond || warn "run: omarchy theme set koi-pond"
elif [[ " ${COMPONENTS[*]} " =~ \ (vlc|chrome)\  ]]; then
  step "Re-applying current theme to render the new templates"
  omarchy theme refresh || warn "re-apply your theme to render the templates"
fi

step "Done"
