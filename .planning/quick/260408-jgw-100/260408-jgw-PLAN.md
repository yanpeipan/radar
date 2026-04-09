---
phase: quick-260408-jgw-100
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - src/llm/evaluator.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "100 iterations complete without crashes"
    - "Each iteration captures quality_score, completeness, Chinese correctness"
    - "Iteration logs saved to ~/.config/feedship/improvement_logs/"
    - "Final summary shows avg quality and common issues"
  artifacts:
    - path: "src/llm/evaluator.py"
      provides: "Enhanced evaluator with completeness and Chinese correctness checks"
    - path: "~/.config/feedship/improvement_logs/"
      provides: "100 iteration JSON logs"
---

<objective>
Run 100-iteration quality improvement loop for AI daily report generation, capturing quality metrics and identifying optimization opportunities.

Purpose: Evaluate report quality across 100 runs, identify failure modes, and provide data-driven improvements.
Output: Iteration logs + summary findings in ~/.config/feedship/improvement_logs/
</objective>

<execution_context>
@/Users/y3/feedship/src/llm/evaluator.py
@/Users/y3/feedship/src/application/report.py
@/Users/y3/feedship/src/cli/report.py
</execution_context>

<context>
## Known Issues from Prior Debugging
1. "Could not classify article layer" warnings - classify_article_layer returns empty occasionally
2. Layer taxonomy: "AI五层蛋糕" - categories: AI应用, AI模型, AI基础设施, 芯片, 能源
3. Database has 2 articles in date range with summaries already generated
4. Quality scoring: 0.50 for both articles

## Five-Layer Categories
- AI应用 (Application)
- AI模型 (Model)
- AI基础设施 (Infrastructure)
- 芯片 (Chip)
- 能源 (Energy)

## Evaluation Criteria
Each iteration must evaluate:
1. **Completeness** - All 5 layers present, each has summary paragraph and at least 1 article
2. **Chinese Correctness** - Summary paragraphs are in proper Chinese (not garbled, no obvious English mixing)
3. **Quality Score** - 0.0-1.0 from LLM evaluation
</context>

<tasks>

<task type="auto">
  <name>Task 1: Enhance evaluator.py with completeness and Chinese correctness checks</name>
  <files>/Users/y3/feedship/src/llm/evaluator.py</files>
  <action>
    Modify `evaluate_report()` in evaluator.py to return enhanced QualityMetrics:

    1. **Completeness Check** - After rendering report, verify all 5 layers exist with content:
       - Each layer section header present (AI应用, AI模型, etc.)
       - Each layer has a non-empty summary paragraph (at least 50 chars)
       - Each layer has at least 1 article listed

    2. **Chinese Correctness Check** - Simple heuristic:
       - Check that summary paragraphs contain Chinese characters (not just English/punctuation)
       - Reject if >50% of summary is non-Chinese characters
       - Flag articles with obvious machine translation artifacts

    3. **Enhanced QualityScore dataclass** - Add fields:
       - completeness (float 0-1)
       - chinese_correctness (float 0-1)
       - layer_breakdown (dict of layer -> completeness bool)

    4. **Error handling** - Wrap evaluation in try/except, return 0.5 defaults on failure

    Replace `evaluate_report()` with enhanced version. Keep `QualityScore` as-is but add new `EnhancedQualityMetrics` that includes it.
  </action>
  <verify>python -c "from src.llm.evaluator import evaluate_report; print('Import OK')"</verify>
  <done>evaluate_report() returns enhanced metrics with completeness and chinese_correctness scores</done>
</task>

<task type="auto">
  <name>Task 2: Run 100-iteration improvement loop with enhanced evaluator</name>
  <files>/Users/y3/feedship/src/llm/evaluator.py</files>
  <action>
    Run the improvement loop using the CLI's built-in command:

    ```bash
    cd /Users/y3/feedship && uv run feedship report --since 2026-04-04 --until 2026-04-10 --run-improvement-loop --iterations 100
    ```

    Before running, verify the evaluator.py changes are wired correctly:
    - `run_improvement_loop()` imports `evaluate_report` - ensure it uses the enhanced version
    - The function saves JSON logs to ~/.config/feedship/improvement_logs/

    If the loop errors out, capture the error and create a fix task.
  </action>
  <verify>Check ~/.config/feedship/improvement_logs/ for iteration_0001.json through iteration_0100.json</verify>
  <done>100 iteration JSON files exist in improvement_logs/</done>
</task>

<task type="auto">
  <name>Task 3: Generate findings summary</name>
  <files>/Users/y3/feedship/.planning/quick/260408-jgw-100/ITERATION_SUMMARY.md</files>
  <action>
    After all 100 iterations complete, generate a summary:

    1. Parse all JSON logs from ~/.config/feedship/improvement_logs/iteration_*.json

    2. Compute aggregated metrics:
       - avg_quality (overall quality score mean)
       - avg_completeness
       - avg_chinese_correctness
       - failure_rate (% of iterations with completeness < 1.0)
       - layer_coverage (which layers most often missing content)

    3. Identify common issues:
       - List all unique issues from "issues" field
       - Count frequency of each issue type

    4. Write summary to .planning/quick/260408-jgw-100/ITERATION_SUMMARY.md with:
       - Aggregated metrics table
       - Top 5 most frequent issues
       - Recommendations for next optimization

    Example summary format:
    ```markdown
    # 100-Iteration Quality Report

    ## Aggregated Metrics
    | Metric | Avg | Min | Max |
    |--------|-----|-----|-----|
    | Quality Score | 0.XX | 0.XX | 0.XX |
    | Completeness | 0.XX | - | - |
    | Chinese Correctness | 0.XX | - | - |

    ## Failure Analysis
    - Completeness failures: X% (Y iterations)
    - Most failed layers: [layer names]

    ## Top Issues
    1. [issue] (N occurrences)
    2. ...

    ## Recommendations
    1. ...
    ```
  </action>
  <verify>ITERATION_SUMMARY.md exists with aggregated metrics</verify>
  <done>Summary document created with actionable recommendations</done>
</task>

</tasks>

<verification>
- All 100 iterations complete (check for iteration_0100.json)
- No unhandled exceptions crash the loop
- Summary document created with real data from logs
</verification>

<success_criteria>
1. 100 iteration logs exist in ~/.config/feedship/improvement_logs/
2. Each log contains: quality_score, completeness, chinese_correctness, issues, report_sample
3. ITERATION_SUMMARY.md created with aggregated metrics and recommendations
</success_criteria>

<output>
After completion, create `.planning/quick/260408-jgw-100/260408-jgw-01-SUMMARY.md`
</output>
