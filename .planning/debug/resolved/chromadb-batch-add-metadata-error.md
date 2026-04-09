---
status: resolved
trigger: "fix ChromaDB batch add failed"
created: 2026-04-01T00:00:00Z
updated: 2026-04-01T00:00:00Z
---

## Current Focus
hypothesis: "_published_at_to_timestamp doesn't handle datetime objects, causing datetime to be passed directly to ChromaDB"
test: "Added datetime handling in _published_at_to_timestamp and defensive str() coercion for title and url"
expecting: "ChromaDB batch add should succeed without error"
next_action: "VERIFIED - Fix complete"

## Symptoms
expected: Embeddings stored in ChromaDB
actual: Error: `argument 'metadatas': Cannot convert Python object to MetadataValue`
errors:
  - "ChromaDB batch add failed: error=argument 'metadatas': Cannot convert Python object to MetadataValue"
  - "Failed to add embeddings for feed YRfIr8KQI7k7n6GVN9yEY: argument 'metadatas': Cannot convert Python object to MetadataValue"
reproduction: "python -m src.cli fetch --all"
started: "Recently started failing"
metadata_fields: "feed_id, title, link, description, published_at, content, author, tags, category"

## Eliminated
- hypothesis: "tags or category being passed as list instead of string"
  evidence: "These fields are not in the metadata dict passed to ChromaDB (only title, url, published_at)"
- hypothesis: "title or url could be non-strings due to feedparser returning unexpected types"
  evidence: "Added defensive str() coercion in add_article_embeddings"

## Evidence
- timestamp: 2026-04-01T00:00:00Z
  checked: "src/storage/vector.py _published_at_to_timestamp function"
  found: "Function handles str, int, and None but NOT datetime objects or floats"
  implication: "If published_at is a datetime object, it would try to parse as string and fail"

- timestamp: 2026-04-01T00:00:00Z
  checked: "src/storage/vector.py add_article_embeddings function"
  found: "title and url are extracted with 'or \"\"' which doesn't convert non-string non-None types"
  implication: "If title or url is a non-string type, it would be passed to ChromaDB causing the error"

## Resolution
root_cause: "_published_at_to_timestamp didn't handle datetime objects or float timestamps. Also, title and url in add_article_embeddings weren't explicitly coerced to strings."
fix: |
  1. Added datetime handling in _published_at_to_timestamp:
     - if isinstance(published_at, datetime): return int(published_at.timestamp())
  2. Added float handling in _published_at_to_timestamp:
     - if isinstance(published_at, (int, float)): return int(published_at)
  3. Added defensive string coercion for title and url in add_article_embeddings:
     - title = str(title) if title else ""
     - url = str(url) if url else ""
verification: |
  - Ran 'python -m src.cli fetch --all' - no ChromaDB error, 38 articles fetched
  - Semantic search returns results correctly
files_changed:
  - "src/storage/vector.py"
