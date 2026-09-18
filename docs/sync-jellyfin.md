# sync-jellyfin.sh

Copies new movies and series from local storage to a Jellyfin library share. It
reorganises TV episodes into the per-season folders Jellyfin expects.

```
/data/movies/<Movie (Year)>/...          ->  /mnt/jellyfin/Movies/<Movie (Year)>/...
/data/series/<Show>/<Show>.S01E02.mkv    ->  /mnt/jellyfin/TV/<Show>/Season 01/<Show>.S01E02.mkv
```

The source is only read, never changed. Files that already exist on the share are skipped.

## Install

```sh
./install.sh jellyfin      # -> ~/.local/bin/sync-jellyfin.sh (needs rsync)
```

## Usage

```sh
sync-jellyfin.sh -n   # dry run: show what would be copied
sync-jellyfin.sh      # copy
sync-jellyfin.sh -v   # verbose, per-file progress
sync-jellyfin.sh -q   # quiet, warnings and summary only
```

## Configuration

These environment variables override the default paths:

| Variable | Default |
|---|---|
| `SRC_MOVIES` | `/data/movies` |
| `SRC_SERIES` | `/data/series` |
| `DST_ROOT` | `/mnt/jellyfin` (must contain `Movies/` and `TV/`) |
| `LOCKFILE` | `/tmp/sync-jellyfin.lock` |

The script doesn't mount the share. Set that up yourself (for example CIFS via
autofs or fstab, with credentials in a root-only credentials file). Don't put
credentials in this repo.

## Notes

- Episodes are grouped by the `SxxEyy` tag in the filename. Files without one
  are skipped with a warning.
- The copy is made for SMB/CIFS: it doesn't sync owner or permissions, and it
  allows a 2-second timestamp difference.
- Unfinished copies go into a hidden `.rsync-partial/` folder, so Jellyfin never
  picks up a half-copied episode.
- A lock file stops two syncs from running at the same time.
