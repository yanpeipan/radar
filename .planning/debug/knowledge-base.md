# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## chromadb-batch-add-metadata-error — ChromaDB batch add failed with MetadataValue conversion error
- **Date:** 2026-04-01
- **Error patterns:** chromadb, MetadataValue, Cannot convert Python object, batch add
- **Root cause:** `_published_at_to_timestamp` didn't handle datetime objects or float timestamps. ChromaDB requires metadata values to be strings, ints, or floats.
- **Fix:** Added datetime handling (`isinstance(published_at, datetime)`) and float handling (`isinstance(published_at, int | float)`) in `_published_at_to_timestamp`. Also added defensive `str()` coercion for `title` and `url` in `add_article_embeddings`.
- **Files changed:** src/storage/vector.py
---

## nitterprovider-fetch-zero-articles — NitterProvider returns 0 articles with "All Nitter instances failed"
- **Date:** 2026-04-01
- **Error patterns:** NitterProvider, All Nitter instances failed, fetch zero articles, nitter:elonmusk
- **Root cause:** Three bugs: (1) config.py path wrong - used src/config.yaml instead of config.yaml, (2) nitter_provider.py import typo - scrapling_utils vs scraping_utils, (3) scraping_utils.py StealthyFetcher didn't use system proxy causing timeouts
- **Fix:** Fixed config.py path to parent.parent.parent, fixed import typo, added _get_proxy() function to pass proxy to StealthyFetcher
- **Files changed:** src/application/config.py, src/providers/nitter_provider.py, src/utils/scraping_utils.py
---

## article-list-count-has-more-bug — article list --json --limit 1 returns has_more=false when count=1
- **Date:** 2026-04-06
- **Error patterns:** has_more, count, limit, article list, json output
- **Root cause:** In format_article_list(), has_more was calculated as `len(items) > limit` instead of `len(items) >= limit`. When exactly limit items are returned, has_more should be true to indicate more results exist.
- **Fix:** Changed has_more condition from `len(items) > limit` to `len(items) >= limit` in src/cli/ui.py
- **Files changed:** src/cli/ui.py
---

## entity-cluster-quality-score — TypeError when summing quality_score in entity_cluster.py
- **Date:** 2026-04-11
- **Error patterns:** TypeError, unsupported operand type, int and NoneType, entity_cluster, quality_score sum
- **Root cause:** sum() in entity_cluster.py cannot add int + None. quality_score is legitimately NULL in the database for some articles, and the code didn't handle this.
- **Fix:** Replace `a.quality_score` with `a.quality_score or 0` in all three sum() calls (lines 73, 139, 156)
- **Files changed:** src/application/report/entity_cluster.py
---
