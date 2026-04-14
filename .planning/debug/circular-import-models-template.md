---
status: awaiting_human_verify
trigger: "ImportError - cannot import 'ReportData' from partially initialized module 'src.application.report.models' due to circular import between models.py and template.py"
created: 2026-04-12T00:00:00Z
updated: 2026-04-12T00:00:00Z
---

## Current Focus

hypothesis: Fixed - Both files now use TYPE_CHECKING to defer type-only imports
test: Verified with `uv run python -c "from src.application.report.models import ReportData; print('models.py OK')"`
expecting: Circular import resolved
next_action: Awaiting user verification with actual report command

## Symptoms

expected: `uv run feedship report --since 2026-04-08 --until 2026-04-10 --language zh` runs without import errors
actual: ImportError on startup - circular import between models.py and template.py
errors:
```
File "/Users/y3/feedship/src/application/report/generator.py", line 13, in <module>
    from src.application.report.models import ReportArticle, ReportCluster, ReportData
File "/Users/y3/feedship/src/application/report/models.py", line 10, in <module>
    from src.application.report.template import HeadingNode
File "/Users/y3/feedship/src/application/report/template.py", line 11, in <module>
    from .models import ReportData
ImportError: cannot import name 'ReportData' from partially initialized module 'src.application.report.models'
```
reproduction: `uv run feedship report --since 2026-04-08 --until 2026-04-10 --language zh`
started: After recent refactors that added `build()` method using HeadingNode

## Evidence

- timestamp: 2026-04-12
  checked: models.py
  found: Line 10 had `from src.application.report.template import HeadingNode` at module level. Line 111 uses `HeadingNode | None` as type hint in dataclass field
  implication: HeadingNode is only used for type annotation, not runtime

- timestamp: 2026-04-12
  checked: template.py
  found: Line 11 had `from .models import ReportData` at module level. Line 112 uses `ReportData` as type hint in `render` method signature
  implication: ReportData is only used for type annotation, not runtime

- timestamp: 2026-04-12
  checked: generator.py
  found: Line 9-10 uses TYPE_CHECKING for HeadingNode import - correctly defers non-type-check import
  implication: generator.py already uses correct pattern, models.py and template.py should follow same pattern

- timestamp: 2026-04-12
  checked: After fix
  found: All three modules import successfully without circular import error
  implication: Fix verified

## Eliminated

## Resolution

root_cause: Both models.py and template.py imported each other's classes at module level for use in type hints. This created a circular dependency when generator.py tried to import from models.py. models.py would start loading, then try to import HeadingNode from template.py, which would in turn try to import ReportData from models.py before it was fully initialized.

fix: Changed both `models.py` and `template.py` to use `TYPE_CHECKING` guard for these imports, which are only used for type annotations and not at runtime.

verification: Verified with direct Python imports - all modules now load without ImportError
files_changed:
- src/application/report/models.py
- src/application/report/template.py
