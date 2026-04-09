# Phase: AI Report Generation - 10 Iteration Evaluation

**Researched:** 2026-04-08
**Domain:** AI newsletter report generation using Five-Layer Cake taxonomy
**Confidence:** HIGH (based on 20 logged iterations + 1 live run with provider failures)

## Summary

The report generation pipeline has **two critical system failures** that make quality assessment impossible: (1) all LLM providers are rate-limited/failing, causing layer summaries to be empty (`（暂无总结）`) or missing entirely; (2) the quality evaluator returns all-0.5 fallback scores. Beyond the provider issues, the 5-layer taxonomy has boundary ambiguity between AI应用 and AI基础设施, and the 芯片/能源 layers are consistently empty. The improvement loop across 20 iterations produces identical output, indicating it is not actually introducing variation.

## AI Architect Perspective

### Five-Layer Taxonomy Evaluation

| Layer | Status | Issue |
|-------|--------|-------|
| AI应用 | Working | Boundary unclear - where does "AI-powered product" end and "AI model API" begin? |
| AI模型 | Working | Papers often equally about "research" vs "model architecture" - no AI研究 layer |
| AI基础设施 | Working | MLOps/deployment blends with 应用 layer |
| 芯片 | EMPTY | No articles classified here - either feed doesn't cover hardware OR classification failing |
| 能源 | EMPTY | No articles classified here - same diagnosis |

**Missing layer analysis:** The taxonomy lacks an **AI研究/学术** (AI Research/Academia) layer. Papers about reasoning chains, latent generalization, preference instability, etc. are categorized as "AI模型" but they are fundamentally research/academic contributions, not model releases. A separate research layer would improve topical clustering.

**Boundary ambiguity:** The distinction between AI应用 and AI基础设施 is fuzzy. "Horizon-LM: A RAM-Centric Architecture for LLM Training" is classified under AI基础设施, but it could equally be AI模型 (architecture research). The classification prompt does not disambiguate.

**Hardware/Energy layers empty:** Most likely cause is the RSS feeds do not cover chip/energy topics. Secondarily, if classification is too loose, articles about NVIDIA GPU training might be misclassified into AI模型 instead of 芯片.

### Classification Chain Analysis

The classification chain is **working** - different articles appear in different layers, meaning the LLM is successfully categorizing. The issue is purely in summary generation.

```
CLASSIFY_PROMPT → AsyncLLMWrapper → StrOutputParser()
```

**Root cause of empty summaries:** `generate_cluster_summary()` calls `get_layer_summary_chain().ainvoke()` which invokes the LLM. With all providers failing (rate limits, 529 overload, InternalServerError), the chain throws an exception caught by the try/except, returning `"（暂无总结）"`.

**Fix required:** Implement retry logic with exponential backoff in `generate_cluster_summary()`, or queue failed summaries for later generation.

## AI Journalist Perspective

### Report Format Issues

1. **Empty summary placeholders:** `（暂无总结）` is a developer error message, not professional journalism. Should be hidden from output entirely, or replaced with "本周无重大进展" style editorial copy.

2. **Blank lines in output:** The report shows:
   ```
   ### 1. AI应用
   
   
   
   
   - [Article1]...
   ```
   The 4-5 blank lines between header and article list indicate the summary is empty/missing. This is visually jarring and unprofessional.

3. **Quality scores are meaningless:** Every article shows `(q=0.50)` which is the fallback default value, not an actual quality assessment. Either:
   - Remove quality scores from display when they're default values
   - Or implement actual quality scoring

4. **No editorial context:** The report lacks:
   - Date of generation
   - Number of sources/sources listed
   - Time period context
   - Executive summary or headline trends

### Chinese Quality Assessment

**Cannot assess fully** because summaries are missing. However:
- Article titles are English (e.g., "TDA-RC: Task-Driven Alignment...") - acceptable for technical audience but could use Chinese translations
- The `（暂无总结）` placeholder is in Chinese but is a placeholder, not editorial content

### Editorial Improvements Needed

| Issue | Fix |
|-------|-----|
| Empty sections show placeholder | Conditionally hide sections with no content, or show "本周暂无相关内容" |
| No trend narrative | Add an executive summary paragraph before the 5 layers |
| Quality scores all 0.50 | Either implement real scoring or remove from display |
| Article titles in English | Consider adding Chinese titles/descriptions |

## Process Evaluation: 10 Iterations vs 20 Logged

| Iteration | Summary Status | Quality Scores | Variation |
|-----------|---------------|----------------|-----------|
| 1-5 (logged) | All empty, identical | All 0.50 | None |
| 6-10 (logged) | All empty, identical | All 0.50 | None |
| 11-20 (logged) | All empty, identical | All 0.50 | None |
| Live run #1 | AI应用=empty, AI模型/AI基础设施=（暂无总结）, 芯片/能源=absent | All 0.50 | Same as logged |

**Finding:** The improvement loop is not improving anything. All 20 iterations produce identical reports. This is because:
1. The data source is static (pre-fetched articles don't change)
2. The LLM calls all fail identically due to rate limits
3. No randomness or variation is introduced between iterations

**The improvement loop needs purpose.** Currently it runs but doesn't actually improve anything.

## Specific Issues Found

### Issue 1: All Layer Summaries Empty
**Severity:** CRITICAL
**Symptom:** Reports show 4-5 blank lines before article lists, or `（暂无总结）` placeholder
**Root cause:** LLM provider failures (rate limits, 529 overload, InternalServerError) cause `generate_cluster_summary()` to throw, caught by except, returns fallback
**Fix:** Add retry with exponential backoff to `generate_cluster_summary()`, or batch failed summaries for retry

### Issue 2: Quality Scores All 0.50
**Severity:** CRITICAL
**Symptom:** All quality dimensions show 0.50 in evaluation logs
**Root cause:** `evaluate_report()` chain returns non-JSON response, falls back to float parsing which also fails, returns default 0.5
**Fix:** Verify the EVALUATE_PROMPT returns valid JSON, or fix the evaluation chain

### Issue 3: Improvement Loop Has No Effect
**Severity:** HIGH
**Symptom:** 20 iterations produce identical reports
**Root cause:** `run_improvement_loop()` calls the same functions with same parameters - no variation introduced
**Fix:** Either implement actual prompt mutation between iterations, or remove this feature

### Issue 4: 芯片 and 能源 Layers Completely Absent
**Severity:** MEDIUM
**Symptom:** Only AI应用, AI模型, AI基础设施 appear in reports
**Root cause:** Either (a) feeds don't cover these topics, or (b) classification failing silently for these topics
**Fix:** Audit feeds for hardware/energy content, improve classification prompt

### Issue 5: Empty Lines in Template Output
**Severity:** MEDIUM
**Symptom:** Visual blank lines between section headers and content
**Root cause:** Summary strings are empty (`""`) but template still renders them as blank lines
**Fix:** Use `{% if summary %}{{ summary }}{% endif %}` in template instead of unconditional `{{ summary }}`

### Issue 6: Quality Score in Article List is Meaningless
**Severity:** LOW
**Symptom:** `(q=0.50)` shown for every article
**Root cause:** Default fallback value, not actual evaluation
**Fix:** Only show quality score if it differs from default (e.g., `{% if article.quality_score and article.quality_score != 0.5 %}`)

## Code Locations for Fixes

| Issue | File | Function/Line |
|-------|------|---------------|
| Empty summaries | `src/application/report.py` | `generate_cluster_summary()` line 54-78 |
| Blank lines in template | `src/application/report.py` | `_DEFAULT_TEMPLATE_MARKDOWN` line 259 - use `{% if summary %}` |
| Quality evaluator | `src/llm/evaluator.py` | `evaluate_report()` line 61-103 |
| Improvement loop | `src/llm/evaluator.py` | `run_improvement_loop()` line 273-369 |
| Classification prompt | `src/llm/chains.py` | `CLASSIFY_PROMPT` line 87-103 |

## Layer Summary Prompt Analysis

```python
LAYER_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are writing a concise summary for a news report section."),
    ("human", """The following articles are about: {layer}
Articles:
{article_list}
Write 2-3 paragraphs summarizing the key trends and insights from these articles.
Focus on the most important developments. Use professional Chinese.
Summary:"""),
])
```

**Issues:**
1. "2-3 paragraphs" is vague - might return 1 paragraph or 5
2. No instruction to separate trends from individual article highlights
3. No instruction to cite article titles in the summary
4. No instruction on tone (professional news vs academic)

**Suggested improvement:**
```
Write 2-3 paragraphs in professional Chinese news style.
Paragraph 1: Major trend or headline (1-2 sentences)
Paragraph 2: Key developments with specific article citations (3-4 sentences)
Paragraph 3: Forward-looking insight or implication (1-2 sentences)
Do NOT list articles again - synthesize them.
```

## Classification Prompt Analysis

```python
CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Classify this article into ONE of the following categories:
- AI应用 (Application): AI products, tools, and services used by end users
- AI模型 (Model): AI model releases, benchmarks, research papers, training methods
- AI基础设施 (Infrastructure): Cloud platforms, MLOps tools, deployment, APIs
- 芯片 (Chip): AI hardware, GPUs, custom silicon, semiconductor news
- 能源 (Energy): AI energy consumption, data center power, carbon, renewable energy"""),
    ("human", "Article Title: {title}\nArticle Content: {content}\n\nReturn ONLY the category name."),
])
```

**Issues:**
1. "AI模型: research papers" overlaps with "AI应用" when papers describe products
2. "AI基础设施: deployment, APIs" overlaps with "AI应用: tools and services"
3. No guidance on what to do with multi-topic articles
4. No guidance on research papers about infrastructure (e.g., papers about distributed training)

**Missing category:** AI研究/学术 (research/academia papers specifically)

## Recommendations Priority

1. **CRITICAL:** Fix layer summary generation with retry logic
2. **CRITICAL:** Debug why quality evaluator returns 0.5 for everything
3. **HIGH:** Audit why 芯片 and 能源 are always empty
4. **HIGH:** Implement actual variation in improvement loop
5. **MEDIUM:** Fix template to hide empty summaries
6. **MEDIUM:** Add executive summary section to report
7. **LOW:** Add Chinese translation hints to classification
