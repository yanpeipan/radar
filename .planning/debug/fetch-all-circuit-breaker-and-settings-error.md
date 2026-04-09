---
status: investigating
trigger: "feedship fetch --all produces: RuntimeWarning coroutine not awaited, FeedshipSettings has no attribute 'get', Malformed feed detected"
created: 2026-04-02T00:00:00Z
updated: 2026-04-02T00:00:00Z
---

## Current Focus
hypothesis: "Three independent bugs introduced by Pydantic migration: (1) async can_execute called via asyncio.to_thread without proper await, (2) settings.get() called on Pydantic model instead of nested dict, (3) malformed feed is consequence of circuit bypass"
test: "Fix each bug and verify fetch --all works"
expecting: "After fixes: async properly awaited, settings accessed correctly, circuit breaker functioning"
next_action: "Verify fixes by running tests and feedship fetch --all"

## Symptoms
expected: "feedship fetch --all fetches all subscribed feeds successfully"
actual: "Command fails with three errors: async warning, attribute error, and malformed feed"
errors:
  - "RuntimeWarning: coroutine 'CircuitBreakerState.can_execute' was never awaited"
  - "'FeedshipSettings' object has no attribute 'get'"
  - "Malformed feed detected: <unknown>:2:281: mismatched tag"
reproduction: "Run `feedship fetch --all`"
started: "Appeared after Phase 5 (Pydantic migration) and Phase 6 (security hardening)"

## Eliminated

## Evidence
- timestamp: 2026-04-02T00:00:00Z
  checked: "fetch.py line 70: `if not await asyncio.to_thread(circuit.can_execute):`"
  found: "can_execute is an async method (line 152 in scraping_utils.py). Passing it to asyncio.to_thread() returns the coroutine object without awaiting it. Coroutines are truthy, so circuit check is bypassed."
  implication: "Circuit breaker never works - requests proceed even when circuit should be open"

- timestamp: 2026-04-02T00:00:00Z
  checked: "nitter_provider.py lines 158-159 and scraping_utils.py line 474"
  found: "Both call settings.get('nitter.default_instance') and settings.get('rate_limit.requests_per_minute', 10.0). Pydantic BaseSettings does not have a .get() method - it was using Dynaconf's dot-notation access."
  implication: "AttributeError raised when trying to access nitter or rate_limit settings"

- timestamp: 2026-04-02T00:00:00Z
  checked: "scraping_utils.py CircuitBreakerState.can_execute is async (line 152)"
  found: "async method uses 'async with self._lock' for thread safety, but being called via asyncio.to_thread() defeats the purpose since it runs in a thread pool"
  implication: "Locking in async context via asyncio.to_thread is incorrect pattern"

## Resolution
root_cause: "Three bugs from Pydantic migration: (1) async can_execute passed to asyncio.to_thread instead of being awaited directly, (2) settings.get() called on Pydantic model instead of nested dict.get(), (3) circuit bypassed caused malformed feeds to propagate"
fix:
  - "fetch.py: Changed `await asyncio.to_thread(circuit.can_execute)` to `await circuit.can_execute()`"
  - "nitter_provider.py: Changed `settings.get('nitter.default_instance')` to `settings.nitter.get('default_instance')`"
  - "nitter_provider.py: Changed `settings.get('nitter.instances', [])` to `settings.nitter.get('instances', [])`"
  - "scraping_utils.py: Changed `settings.get('rate_limit.requests_per_minute', 10.0)` to `settings.rate_limit.get('requests_per_minute', 10.0)`"
verification: "104 tests pass, circuit breaker async works, settings access works, syntax check passed"
files_changed:
  - "src/application/fetch.py"
  - "src/providers/nitter_provider.py"
  - "src/utils/scraping_utils.py"
