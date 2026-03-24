# Phase 19: uvloop Setup + crawl_async Protocol - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped — infrastructure phase)

<domain>
## Phase Boundary

Async crawl capability available on all providers. This is the foundation phase for uvloop integration — it sets up the event loop and defines the async crawl protocol that all providers will implement.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use uvloop best practices and existing codebase conventions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase success criteria:
1. uvloop.install() called at startup on Linux/macOS
2. uvloop.install() fails gracefully on Windows (falls back to asyncio)
3. ContentProvider protocol has crawl_async() method
4. Default crawl_async() wraps sync crawl() in run_in_executor
5. Non-main thread uvloop errors caught gracefully

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
