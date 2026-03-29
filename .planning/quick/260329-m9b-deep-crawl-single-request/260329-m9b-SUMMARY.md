# Quick Task 260329-m9b: Deep Crawl Single Request

## Summary

Merged `_quick_validate_feed` and `_extract_feed_title` into `_validate_and_extract_title` - single HTTP request instead of two.

## Changes

### Before (2 requests for direct feed URL)
```python
is_valid_feed, feed_type = await _quick_validate_feed(start_url)
if is_valid_feed:
    title = await _extract_feed_title(start_url)  # 2nd request!
```

### After (1 request)
```python
is_valid_feed, feed_type, title = await _validate_and_extract_title(start_url)
```

## Verification

- `_validate_and_extract_title('https://openai.com/news/rss.xml')` → `(True, 'rss', 'OpenAI News')` ✅
- `_quick_validate_feed` still works via delegation ✅
- All 24 provider tests pass ✅

## Commit

`refactor(260329-m9b): merge validate+title into single request`
