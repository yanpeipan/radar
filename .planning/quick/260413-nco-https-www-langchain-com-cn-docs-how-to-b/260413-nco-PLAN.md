---
phase: quick
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - src/application/report/classify.py
  - src/application/report/generator.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "BatchClassifyChain is replaced with RunnableLambda factory"
    - "generator.py uses new factory instead of class"
    - "Existing retry logic preserved (529 handled by LLMWrapper)"
  artifacts:
    - path: "src/application/report/classify.py"
      provides: "get_classify_runnable() factory function"
      contains: "RunnableLambda"
    - path: "src/application/report/generator.py"
      provides: "Uses new factory function"
      contains: "get_classify_runnable"
  key_links:
    - from: "src/application/report/generator.py"
      to: "src/application/report/classify.py"
      via: "get_classify_runnable()"
---

<objective>
Refactor BatchClassifyChain from class-based Runnable to LCEL RunnableLambda factory pattern, per research findings.
</objective>

<context>
@src/application/report/classify.py (current BatchClassifyChain implementation)
@src/application/report/generator.py (consumer of BatchClassifyChain)
</context>

<interfaces>
<!-- From src/llm/chains.py -->
```python
def get_classify_translate_chain(tag_list: str, news_list: str, target_lang: str) -> Runnable:
    ...
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create get_classify_runnable factory function</name>
  <files>src/application/report/classify.py</files>
  <action>
Add `get_classify_runnable()` factory function that returns a RunnableLambda:

```python
def get_classify_runnable(
    tag_list: str,
    target_lang: str,
    batch_size: int = 50,
    max_concurrency: int = 5,
) -> Runnable:
    """Factory: returns RunnableLambda that processes list[ArticleListItem] -> list[ArticleListItem].

    Batching: split input into batches of batch_size, process max_concurrency batches concurrently.
    Each batch calls get_classify_translate_chain, enriches articles in-place with .tags and .translation.
    """
    async def classify_fn(input: list[ArticleListItem]) -> list[ArticleListItem]:
        # Split input into batches
        batches = [(input[i:i + batch_size], i) for i in range(0, len(input), batch_size)]
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_with_semaphore(
            batch_articles: list[ArticleListItem], batch_offset: int
        ) -> list[ClassifyTranslateItem]:
            async with semaphore:
                try:
                    # Build news_list and call chain
                    news_list = "\n".join(
                        f"{j + 1}. {art.title or ''}" for j, art in enumerate(batch_articles)
                    )
                    from src.llm.chains import get_classify_translate_chain
                    chain = get_classify_translate_chain(
                        tag_list=tag_list,
                        news_list=news_list,
                        target_lang=target_lang,
                    )
                    output = await chain.ainvoke({
                        "tag_list": tag_list,
                        "news_list": news_list,
                        "target_lang": target_lang,
                    })
                    # Adjust IDs for batch offset
                    for item in output.items:
                        item.id += batch_offset
                    return output.items
                except Exception as e:
                    logger.warning("Batch %d failed: %s", batch_offset, e)
                    return []

        batch_results = await asyncio.gather(
            *[run_with_semaphore(arts, offset) for arts, offset in batches]
        )

        # Flatten and build lookup dicts
        all_items: list[ClassifyTranslateItem] = []
        for batch_items in batch_results:
            all_items.extend(batch_items)

        trans_by_id = {item.id: item.translation for item in all_items}
        tags_by_id = {item.id: item.tags for item in all_items}

        # Enrich original articles in-place
        for idx, art in enumerate(input, 1):
            art.tags = tags_by_id.get(idx, [])
            art.translation = trans_by_id.get(idx)

        return input

    return RunnableLambda(classify_fn)
```

Keep `BatchClassifyChain` class at end of file (DEPRECATED) for backward compatibility - do NOT remove.
  </action>
  <verify>
    <automated>cd /Users/y3/feedship && uv run python -c "from src.application.report.classify import get_classify_runnable; print('import OK')"</automated>
  </verify>
  <done>get_classify_runnable() factory function exists, imports without error</done>
</task>

<task type="auto">
  <name>Task 2: Update generator.py to use factory</name>
  <files>src/application/report/generator.py</files>
  <action>
In generator.py, find where BatchClassifyChain is instantiated:
```python
from src.application.report.classify import BatchClassifyChain
# ...
batch_classify = BatchClassifyChain(...)
```

Replace with:
```python
from src.application.report.classify import get_classify_runnable
# ...
batch_classify = get_classify_runnable(...)
```

Keep all same parameters (tag_list, target_lang, batch_size, max_concurrency).
  </action>
  <verify>
    <automated>uv run python -c "from src.application.report.generator import generate_report_async; print('import OK')"</automated>
  </verify>
  <done>generator.py imports and uses get_classify_runnable instead of BatchClassifyChain class</done>
</task>

</tasks>

<verification>
- `uv run python -c "from src.application.report.classify import get_classify_runnable; print('OK')"` passes
- `uv run python -c "from src.application.report.generator import generate_report_async; print('OK')"` passes
</verification>

<success_criteria>
- get_classify_runnable() factory returns RunnableLambda that matches original BatchClassifyChain behavior
- generator.py uses factory instead of class
- BatchClassifyChain class preserved for backward compatibility
- No changes to LLMWrapper retry logic (529 already handled)
</success_criteria>

<output>
After completion, create `.planning/quick/260413-nco-https-www-langchain-com-cn-docs-how-to-b/260413-nco-SUMMARY.md`
</output>
