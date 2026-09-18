#!/usr/bin/env bash
#
# sync-jellyfin.sh -- copy new movies and series from /data to the Jellyfin share.
#
#   /data/movies/<Movie (Year)>/...          ->  /mnt/jellyfin/Movies/<Movie (Year)>/...
#   /data/series/<Show>/<Show>.S01E02.mkv    ->  /mnt/jellyfin/TV/<Show>/Season 01/<Show>.S01E02.mkv
#
# Series are stored flat in /data but Jellyfin prefers per-season folders, so the
# season directory is created on the destination side. /data is never modified.
#
# Only movies and series are synced; downloads/ and games/ are ignored.
#
# Usage: sync-jellyfin.sh [-n] [-v] [-q]
#   -n  dry run, show what would be copied without writing anything
#   -v  verbose, list every file rsync considers
#   -q  quiet, only warnings and the final summary

set -euo pipefail

SRC_MOVIES=${SRC_MOVIES:-/data/movies}
SRC_SERIES=${SRC_SERIES:-/data/series}
DST_ROOT=${DST_ROOT:-/mnt/jellyfin}
DST_MOVIES="$DST_ROOT/Movies"
DST_TV="$DST_ROOT/TV"
LOCKFILE=${LOCKFILE:-/tmp/sync-jellyfin.lock}

DRY_RUN=0
VERBOSE=0
QUIET=0

while getopts ":nvqh" opt; do
    case "$opt" in
        n) DRY_RUN=1 ;;
        v) VERBOSE=1 ;;
        q) QUIET=1 ;;
        h) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown option -$OPTARG (try -h)" >&2; exit 2 ;;
    esac
done

log()  { [ "$QUIET" = 1 ] || printf '%s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Only one sync at a time: a second run while a big copy is in flight would
# fight over the same partial files.
exec 9>"$LOCKFILE"
flock -n 9 || die "another sync is already running (lock: $LOCKFILE)"

# The share is an autofs/CIFS mount; touching it wakes it up.
[ -d "$SRC_MOVIES" ] || die "missing source $SRC_MOVIES"
[ -d "$SRC_SERIES" ] || die "missing source $SRC_SERIES"
mountpoint -q "$DST_ROOT" || ls "$DST_ROOT" >/dev/null 2>&1 || true
[ -d "$DST_MOVIES" ] || die "missing destination $DST_MOVIES (is the share mounted?)"
[ -d "$DST_TV" ]     || die "missing destination $DST_TV (is the share mounted?)"

# CIFS cannot store unix ownership or permissions, so don't try to sync them --
# rsync would report a failure on every single file. Timestamps on SMB have a
# coarser resolution, hence the modify-window. Partial transfers go to a hidden
# sibling directory so an interrupted copy never looks like a complete episode.
RSYNC_OPTS=(
    --recursive
    --times
    --no-perms --no-owner --no-group
    --modify-window=2
    --partial --partial-dir=.rsync-partial
    --human-readable
    --stats
)
[ "$DRY_RUN" = 1 ] && RSYNC_OPTS+=(--dry-run)
if [ "$VERBOSE" = 1 ]; then
    RSYNC_OPTS+=(--verbose --progress)
elif [ "$QUIET" = 1 ]; then
    RSYNC_OPTS+=(--quiet)
else
    RSYNC_OPTS+=(--itemize-changes)
fi

[ "$DRY_RUN" = 1 ] && log "== DRY RUN -- nothing will be written =="

copied=0
skipped=0

# ---------------------------------------------------------------- movies ----
log
log "== Movies: $SRC_MOVIES -> $DST_MOVIES"
if rsync "${RSYNC_OPTS[@]}" "$SRC_MOVIES/" "$DST_MOVIES/"; then
    copied=$((copied + 1))
else
    warn "movie sync reported errors (exit $?)"
fi

# ---------------------------------------------------------------- series ----
# One rsync per show/season: cheaper than one call per episode over SMB, and it
# lets rsync skip everything already present without a round trip per file.
log
log "== Series: $SRC_SERIES -> $DST_TV"

shopt -s nullglob
for show_dir in "$SRC_SERIES"/*/; do
    show=$(basename "$show_dir")

    # Group this show's files by season number parsed from the SxxEyy tag.
    declare -A season_files=()
    for f in "$show_dir"*; do
        [ -f "$f" ] || continue
        name=$(basename "$f")
        if [[ $name =~ [Ss]([0-9]{1,3})[Ee][0-9]{1,3} ]]; then
            season=$(printf '%02d' "$((10#${BASH_REMATCH[1]}))")
            season_files[$season]+="$name"$'\n'
        else
            warn "no SxxEyy in name, skipped: $show/$name"
            skipped=$((skipped + 1))
        fi
    done

    if [ ${#season_files[@]} -eq 0 ]; then
        warn "no episodes found in $show"
        unset season_files
        continue
    fi

    for season in $(printf '%s\n' "${!season_files[@]}" | sort); do
        dest="$DST_TV/$show/Season $season"
        log "-- $show / Season $season"
        if [ "$DRY_RUN" = 0 ]; then
            mkdir -p "$dest" || { warn "cannot create $dest"; continue; }
        fi
        # --files-from reads the episode list on stdin, relative to the show dir.
        if printf '%s' "${season_files[$season]}" \
            | rsync "${RSYNC_OPTS[@]}" --files-from=- "$show_dir" "$dest/"; then
            copied=$((copied + 1))
        else
            warn "sync failed for $show / Season $season (exit $?)"
        fi
    done
    unset season_files
done

log
log "== Done. $copied transfer group(s) processed, $skipped file(s) skipped."
[ "$skipped" -gt 0 ] && log "   Skipped files had no SxxEyy episode tag -- rename them and re-run."
exit 0
