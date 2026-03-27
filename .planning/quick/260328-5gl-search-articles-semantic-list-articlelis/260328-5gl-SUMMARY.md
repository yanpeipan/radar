# Summary: 260328-5gl - search_articles_semantic returns list[ArticleListItem]

## Completed

- `rank_semantic_results()` in `src/application/search.py` now includes `feed_id` and `feed_name` in returned dicts (lines 200-201)
- `search_articles_semantic()` in `src/storage/vector.py` now returns `list[ArticleListItem]` instead of `list[dict]`
- `ArticleListItem` imported from `src.application.articles`
- `format_semantic_results` import removed from `vector.py` (no longer needed)
- `ArticleListItem` objects constructed with all required fields: `id`, `feed_id`, `feed_name`, `title`, `link`, `guid`, `pub_date`, `description=None`, `score`

## Files Modified

- `src/application/search.py` - rank_semantic_results adds feed_id/feed_name to ranked result dicts
- `src/storage/vector.py` - search_articles_semantic returns list[ArticleListItem]

## Verification

- Python syntax verified: `python -m py_compile` passes for both files
- `grep -n "feed_id.*article.feed_id" src/application/search.py` returns line 200
- `grep -n "ArticleListItem" src/storage/vector.py` shows import and construction at lines 161 and 210

## Notes

- Changes were already present in working tree at session start
- Changes are consistent with plan requirements
