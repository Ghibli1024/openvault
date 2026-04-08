# openvault

`openvault` is the canonical repository for the plugin shell and backend skill history behind bookmark and social archive workflows.

Current stable visible plugin entry point:

- `archive-router`

Current internal canonical skills:

- `bilibili`
- `bookmarks`
- `x-likes`
- `xhs`

The plugin no longer keeps per-source wrapper skills. `archive-router` now routes directly to the four canonical backend skills, while Codex UI still exposes only the single `openvault` entry.

## Refreshing The Local Codex Cache

If Codex UI still shows old skill entries after the repo is updated, refresh the local cache clone explicitly:

```bash
python3 scripts/refresh_openvault_cache.py
```

The script reports the cache commit before and after refresh plus the current visible skill count. Use `--dry-run` to inspect without changing the cache clone.

Historical source repositories are being retained temporarily for archive/reference purposes while `openvault` becomes the primary development home.
