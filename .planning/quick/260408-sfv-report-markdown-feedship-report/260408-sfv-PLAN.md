---
phase: quick
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/cli/report.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "Report command auto-saves markdown to ~/.local/share/feedship/reports/ when --output not specified"
    - "User can still see report on console when no --output specified"
  artifacts:
    - path: "src/cli/report.py"
      provides: "Auto-save logic when --output is None"
      min_lines: 10
  key_links:
    - from: "src/cli/report.py"
      to: "~/.local/share/feedship/reports/"
      via: "Path.write_text(report_text)"
      pattern: "platformdirs.user_data_dir.*reports"
---

<objective>
Auto-save report markdown to `~/.local/share/feedship/reports/` when `--output` is not specified.
</objective>

<context>
@/Users/y3/feedship/src/cli/report.py
</context>

<interfaces>
Key excerpt from src/cli/report.py lines 175-180:
```python
        if output:
            Path(output).write_text(report_text)
            console.print(f"[green]Report saved to {output}[/green]")
        else:
            console.print(report_text)
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task: Wire auto-save to default reports directory</name>
  <files>src/cli/report.py</files>
  <action>
Add `import platformdirs` at the top of the file (after existing imports, around line 6).

In the `report` function, replace the output handling block (lines 175-180) with:

```python
        if output:
            output_path = Path(output)
        else:
            # Auto-save to ~/.local/share/feedship/reports/{since}_{until}_{template}.md
            reports_dir = Path(platformdirs.user_data_dir("feedship", appauthor=False)) / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{since}_{until}_{template}.md"
            output_path = reports_dir / filename

        output_path.write_text(report_text)
        console.print(f"[green]Report saved to {output_path}[/green]")
```

The `report_text` is always saved now (regardless of `--output`), and always printed to console (when not `--json`).
</action>
  <verify>
    <automated>grep -n "platformdirs\|reports_dir\|output_path" /Users/y3/feedship/src/cli/report.py</automated>
  </verify>
  <done>Report auto-saves to ~/.local/share/feedship/reports/ when --output not specified; explicit --output still works as before</done>
</task>

</tasks>

<verification>
- `feedship report --since 2026-04-01 --until 2026-04-07` saves to `~/.local/share/feedship/reports/2026-04-01_2026-04-07_default.md`
- `feedship report --since 2026-04-01 --until 2026-04-07 --template v2` saves to `~/.local/share/feedship/reports/2026-04-01_2026-04-07_v2.md`
- `feedship report --since 2026-04-01 --until 2026-04-07 --output custom.md` saves to `custom.md` (unchanged behavior)
</verification>

<success_criteria>
Report command saves markdown to default reports directory when `--output` is not specified, while continuing to print output to console.
</success_criteria>

<output>
After completion, no summary file needed (quick plan).
</output>
