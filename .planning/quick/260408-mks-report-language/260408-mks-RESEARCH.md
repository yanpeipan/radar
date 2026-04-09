# Phase: Add `--language` Flag to Report Generation

**Researched:** 2026/04/08
**Domain:** Report translation pipeline
**Confidence:** HIGH

## Summary

The report generation pipeline currently produces Chinese output. The user wants to add `--language` flag to generate reports in other languages (en, ja, ko). Since article summaries are already stored in Chinese in the database, the most practical approach is to translate the final rendered report (Option B), rather than trying to re-translate at the article or classification level.

**Primary recommendation:** Add a post-rendering translation step that translates layer summaries and template headers, while preserving article titles and links in their original language.

## User Constraints (from quick-task)

### Locked Decisions
- `--language` flag on `report` command
- Supported languages: zh (default), en, ja, ko
- Translation of final report output (not per-article)

### Claude's Discretion
- Implementation approach (chain design, translation point)
- How to handle articles already in target language

### Deferred Ideas (OUT OF SCOPE)
- Per-article language detection and selective translation
- Caching translated reports

## Translation Point Analysis

### Option A: Translate article summaries before classification
**Verdict: Not recommended**
- Problem: Summaries are stored in Chinese in SQLite (via `update_article_llm`)
- Translating before storage would pollute the database with non-Chinese summaries
- Additional LLM calls per article during on-demand summarization
- Double translation risk: English article -> Chinese summary -> target language

### Option B: Translate final report output (RECOMMENDED)
**Verdict: Recommended**
- Works with existing stored Chinese summaries
- Single translation at the end (one call per layer + template headers)
- Minimal LLM overhead: ~6 extra calls for a full report
- Article titles/links stay in original language (often desired)
- Translation units: 5 layer summaries + Jinja2 template headers

### Option C: Bilingual prompts throughout all chains
**Verdict: Not recommended for this phase**
- Requires modifying all chain prompts (classify, summarize, layer summary)
- Doesn't help with already-stored Chinese summaries
- Would require regeneration of all existing summaries to be useful

### Decision: Option B

## Supported Languages

| Code | Language | Template Header Translation |
|------|----------|----------------------------|
| zh   | Chinese  | No translation (default)   |
| en   | English  | Full translation           |
| ja   | Japanese | Full translation           |
| ko   | Korean   | Full translation           |

## Implementation Plan

### File: src/llm/chains.py

Add translation chain:

```python
TRANSLATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a professional translator. Translate the following text to {target_lang}."),
        ("human", "Text:\n{text}\n\nTranslated:"),
    ]
)

def get_translate_chain():
    """Returns LCEL chain for text translation."""
    return TRANSLATE_PROMPT | _get_llm_wrapper() | StrOutputParser()
```

### File: src/application/report.py

Add `translate_report()` function after `render_report()`:

```python
# Language code to display name mapping
LANGUAGE_NAMES = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
}

async def translate_report(report_text: str, target_lang: str) -> str:
    """Translate report text to target language.

    Translates layer summaries and template content.
    Preserves article titles and links as-is.
    """
    if target_lang == "zh":
        return report_text

    chain = get_translate_chain()
    lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)

    # Split report into translatable sections and preserved sections
    # Article links/titles should NOT be translated
    lines = report_text.split("\n")
    translated_lines = []
    in_article_list = False

    for line in lines:
        # Skip article bullet points (contain links)
        if line.strip().startswith("- [") and "](" in line:
            translated_lines.append(line)
            in_article_list = True
        elif line.strip().startswith("###") or line.strip().startswith("##"):
            # Section headers - translate
            translated = await chain.ainvoke({
                "text": line,
                "target_lang": lang_name,
            })
            translated_lines.append(translated)
            in_article_list = False
        elif in_article_list:
            translated_lines.append(line)
        elif line.strip() == "" or line.startswith("#"):
            # Empty lines and main title
            translated_lines.append(line)
        else:
            # Body text (layer summaries) - translate
            translated = await chain.ainvoke({
                "text": line,
                "target_lang": lang_name,
            })
            translated_lines.append(translated)

    return "\n".join(translated_lines)
```

### File: src/cli/report.py

Add `--language` option and wire it up:

```python
@click.option(
    "--language",
    default="zh",
    type=click.Choice(["zh", "en", "ja", "ko"]),
    help="Report language (default: zh)",
)
@click.pass_context
def report(
    ctx: click.Context,
    # ... existing options ...
    language: str,
) -> None:
    # ... existing clustering and rendering ...
    report_text = render_report(data, template_name=template)

    # Translate if needed
    if language != "zh":
        import asyncio
        report_text = asyncio.run(translate_report(report_text, language))

    # ... rest of output logic ...
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Translation | Custom translation API calls | `get_translate_chain()` LCEL | Consistent with existing chain pattern, uses same LLM client with fallback |
| Language detection | Build language detection | LLM handles it implicitly | The model naturally produces correct language; no need to detect first |

## Common Pitfalls

### Pitfall 1: Translating article links/titles
**What goes wrong:** Machine translation corrupts URLs, makes titles unnatural
**How to avoid:** Only translate lines that don't contain `](` pattern (article links)

### Pitfall 2: Double translation for already-Chinese content
**What goes wrong:** Wasting API calls when language is zh
**How to avoid:** Early return in `translate_report()` if `target_lang == "zh"`

### Pitfall 3: Per-article translation during on-demand summarize
**What goes wrong:** Each article gets translated separately, multiplying API costs
**How to avoid:** Keep translation at report level, not article level

## Code Examples

### Translation Chain Usage
```python
# From chains.py
chain = get_translate_chain()
result = await chain.ainvoke({
    "text": "AI模型：本週多家廠商發布新模型",
    "target_lang": "English",
})
# Returns: "AI Models: This week, several vendors released new models"
```

### Post-rendering translation flow
```python
# From cli/report.py
report_text = render_report(data, template_name=template)

if language != "zh":
    report_text = asyncio.run(translate_report(report_text, language))
```

## Architecture Patterns

### Translation happens AFTER rendering
```
cluster_articles_for_report()
    -> render_report()  [Chinese]
    -> translate_report()  [if needed]
    -> output
```

### Async translation with existing patterns
The `translate_report()` function uses `asyncio.run()` at the CLI layer, matching the existing pattern in `cluster_articles_for_report()` which also uses `asyncio.run()`.

## Phase Requirements

> Not a planned phase - quick task. No requirement IDs.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | User wants article titles preserved in original language | Translation approach | Low - this is a design choice, easily changed |
| A2 | Template headers (## AI日班 etc.) should be translated | Implementation | Low - logical extension of the feature |
| A3 | Language parameter passed through CLI only affects output | Design | Low - no plan to change storage layer |

## Open Questions

1. **Should template files themselves be per-language?**
   - Current approach: translate rendered output on-the-fly
   - Alternative: maintain separate template files per language
   - Recommendation: Start with on-the-fly translation; templates are simple

2. **Should article quality scores (q=0.XX) be preserved?**
   - Yes, these are numeric and language-independent
   - Implementation already preserves them

## Validation Architecture

Step 2.6: SKIPPED (no external dependencies - uses existing litellm/LLMClient)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - using existing chain pattern
- Architecture: HIGH - follows existing report generation flow
- Pitfalls: MEDIUM - translation edge cases not tested

**Research date:** 2026/04/08
**Valid until:** 90 days (translation is a stable problem space)
