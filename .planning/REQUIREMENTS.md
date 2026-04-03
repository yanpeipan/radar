# Requirements: v1.5 - Info Command

**Gathered:** 2026-04-03
**Status:** Roadmap pending

---

## INFO-01: Version Display
**User can:** View the installed feedship version
**Details:** Display version string from `importlib.metadata.version("feedship")`. Show as `feedship v{version}` in text mode.

---

## INFO-02: Config Path Display
**User can:** View the configuration file path
**Details:** Display path to `config.yaml` using platformdirs (same path used by `_get_settings()`). Show `Config: {path}` in text mode.

---

## INFO-03: Config Values Display
**User can:** View current configuration values
**Details:** Display all active settings from `_get_settings()` (timezone, bm25_factor, stealth_fetcher_timeout, discovery_timeout, max_articles_per_fetch, etc.). Format as key-value pairs in text mode.

---

## INFO-04: Storage Path Display
**User can:** View the SQLite database file path
**Details:** Display path to SQLite DB using `get_db_path()`. Show `Storage: {path}` in text mode.

---

## INFO-05: Storage Stats
**User can:** View storage statistics (article count, feed count, DB size)
**Details:** Query `SELECT COUNT(*) FROM articles`, `SELECT COUNT(*) FROM feeds`, `os.path.getsize(get_db_path())` for DB size. Display as `Articles: {n}`, `Feeds: {n}`, `DB Size: {size}`.

---

## INFO-06: JSON Output
**User can:** Get machine-readable JSON output for scripting
**Details:** `--json` flag outputs all info as structured JSON using `print_json()`. Follows existing `{"item": {...}}` wrapper pattern. Keys: `version`, `config_path`, `config`, `storage_path`, `storage`.

---

## INFO-07: Filter Flags
**User can:** View only a specific section of info
**Details:** `--version` shows version only. `--config` shows config_path and config values. `--storage` shows storage_path and storage stats. Flags can be combined. `--json` works with any filter.

---

## Out of Scope

| Item | Reason |
|------|--------|
| Provider health checks | Requires network calls, adds complexity |
| ChromaDB vector count | May need full initialization to query |
| Config editing | Separate command, not info's job |
| Real-time monitoring | Read-only command |

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| INFO-01 | 1 | Pending |
| INFO-02 | 1 | Pending |
| INFO-03 | 1 | Pending |
| INFO-04 | 1 | Pending |
| INFO-05 | 1 | Pending |
| INFO-06 | 1 | Pending |
| INFO-07 | 1 | Pending |

---
*Requirements gathered: 2026-04-03*
*Roadmap created: 2026-04-03*
