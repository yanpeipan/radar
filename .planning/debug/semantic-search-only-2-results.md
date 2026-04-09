---
status: awaiting_human_verify
trigger: "feedship search 'AI' --semantic --limit 33 returns only 2 results"
created: 2026-04-05T14:40:00Z
updated: 2026-04-05T15:10:00Z
---

## Current Focus
hypothesis: "ROOT CAUSE CONFIRMED and FIXED - _batch_upsert_articles was generating new IDs for ALL articles but ON CONFLICT keeps existing IDs, causing ChromaDB-SQLite ID mismatch"
test: "Fix verified with test case: IDs now consistent across upserts"
expecting: "New articles will have correct ChromaDB IDs matching SQLite"
next_action: "Human verification needed - confirm fix works and decide on stale ChromaDB cleanup"

## Symptoms
expected: up to 33 results
actual: only 2 results returned (OpenAI News 2025-10-27, Nicholas Carlini 2024-08-01)
errors: none
reproduction: "uvx --python 3.12 feedship search 'AI' --json --limit 33 --semantic"
started: unknown (bug existed in _batch_upsert_articles for unknown duration)

## Eliminated

## Evidence
- timestamp: 2026-04-05T14:45:00Z
  checked: "ChromaDB collection count"
  found: "ChromaDB has 66,268 embeddings, SQLite has only 5,319 articles"
  implication: "ChromaDB has ~12x more entries than SQLite - mostly stale"

- timestamp: 2026-04-05T14:50:00Z
  checked: "SQLite articles have ChromaDB embeddings"
  found: "Out of 50 SQLite articles sampled, 0 have ChromaDB embeddings"
  implication: "Existing SQLite articles don't have ChromaDB embeddings"

- timestamp: 2026-04-05T14:55:00Z
  checked: "ChromaDB query vs SQLite lookup for search 'AI'"
  found: "ChromaDB returns 33 IDs, SQLite get_articles_by_ids only finds 2"
  implication: "31 out of 33 ChromaDB result IDs don't exist in SQLite"

- timestamp: 2026-04-05T15:00:00Z
  checked: "_batch_upsert_articles function implementation"
  found: "Line 314 generates new IDs for ALL articles. INSERT ON CONFLICT keeps existing ID. Returns NEW IDs instead of actual database IDs"
  implication: "BUG CONFIRMED: ChromaDB stores with new ID but SQLite has old ID"

- timestamp: 2026-04-05T15:05:00Z
  checked: "Fix verification with test case"
  found: "After fix, upsert returns same IDs for same articles across multiple calls"
  implication: "Fix works correctly for NEW articles"

- timestamp: 2026-04-05T15:08:00Z
  checked: "Stale ChromaDB entries rate"
  found: "93.9% of sample ChromaDB IDs don't exist in SQLite (stale)"
  implication: "Existing ChromaDB data is mostly invalid - needs cleanup for full recovery"

## Resolution
root_cause: "_batch_upsert_articles generates new nanoid for every article, but uses INSERT...ON CONFLICT which preserves existing IDs for duplicate (feed_id, guid) pairs. The function returned the newly generated IDs instead of querying the actual IDs from the database after the upsert."
fix: "Modified _batch_upsert_articles to query actual database IDs using (feed_id, guid) pairs after the upsert, then return those actual IDs."
verification: "Test case verified: same articles upserted multiple times now return consistent IDs"
files_changed: ["src/storage/sqlite/impl.py"]

## Known Issue After Fix
The existing ChromaDB collection (66k entries) contains mostly stale entries with wrong IDs. The fix prevents NEW issues but doesn't clean up existing stale entries. For semantic search to work optimally:

Option 1 (Recommended): Clear ChromaDB and let it rebuild:
  - rm -rf ~/.local/share/feedship/chroma/
  - New articles fetched will create correct embeddings

Option 2: Wait for gradual recovery:
  - As new articles are fetched with correct IDs, semantic search quality will improve over time
  - But stale entries will continue to waste ChromaDB query slots

## CHECKPOINT REACHED
**Type:** human-verify
**Need verification:** Run `uvx --python 3.12 feedship search 'AI' --semantic --limit 33 --json` and check if results improve after fresh feed fetches

**Self-verified checks:**
- Bug fix verified with test case (IDs consistent across upserts)
- Pre-commit checks pass
- Code change is minimal and targeted

**How to verify end-to-end:**
1. Run `uvx --python 3.12 feedship search 'AI' --semantic --limit 33 --json` - still may show few results (stale ChromaDB)
2. Run `uvx --python 3.12 feedship fetch --all` to fetch fresh articles
3. Run search again - should see improvement as new correct embeddings are created

**Tell me:** "confirmed fixed" OR what's still failing
