---
phase: 04-http-resilience-rate-limiting
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/utils/scraping_utils.py
  - config.yaml
autonomous: true
requirements:
  - RESL-01
  - RESL-03

must_haves:
  truths:
    - "TokenBucket rate limiter enforces 10 req/min per domain by default"
    - "Rate limiter is configurable via settings.rate_limit.requests_per_minute"
    - "CircuitBreakerState class exists with failure tracking and state machine"
  artifacts:
    - path: src/utils/scraping_utils.py
      contains: "class TokenBucket"
      min_lines: 60
    - path: src/utils/scraping_utils.py
      contains: "class CircuitBreakerState"
      min_lines: 80
    - path: config.yaml
      contains: "rate_limit:"
  key_links:
    - from: src/utils/scraping_utils.py
      to: config.yaml
      via: settings.get("rate_limit.requests_per_minute")
---

<objective>
Implement TokenBucket rate limiter (RESL-01) and circuit breaker state infrastructure (RESL-03 foundation).

Purpose: Time-based rate limiting per domain with configurable defaults, plus circuit breaker state machine for provider resilience.
Output: TokenBucket class, CircuitBreakerState class, updated _rate_limit_host(), config.yaml entry
</objective>

<context>
@src/utils/scraping_utils.py:56-68,334-367
@src/providers/base.py:23-29
@config.yaml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement TokenBucket and CircuitBreakerState classes</name>
  <files>src/utils/scraping_utils.py</files>
  <action>
    Add TokenBucket and CircuitBreakerState classes to `src/utils/scraping_utils.py` near line 60 (after existing rate limit globals).

    TokenBucket class:
    ```python
    class TokenBucket:
        """Time-based token bucket rate limiter using time.monotonic().
        
        Refills tokens at a steady rate: requests_per_minute / 60 tokens per second.
        Uses asyncio.Lock for thread-safe token consumption.
        """
        
        def __init__(self, requests_per_minute: float = 10.0):
            self._rate = requests_per_minute / 60.0  # tokens per second
            self._capacity = requests_per_minute
            self._tokens = requests_per_minute
            self._last_refill = time.monotonic()
            self._lock = asyncio.Lock()
        
        async def acquire(self) -> None:
            """Acquire a token, waiting if necessary."""
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                self._last_refill = now
                
                if self._tokens < 1.0:
                    wait_time = (1.0 - self._tokens) / self._rate
                    await asyncio.sleep(wait_time)
                    self._tokens = 0.0
                else:
                    self._tokens -= 1.0
    ```

    CircuitBreakerState class:
    ```python
    class CircuitBreakerState:
        """Circuit breaker per provider with CLOSED/OPEN/HALF_OPEN states.
        
        State machine:
        - CLOSED: Normal operation, tracks consecutive failures
        - OPEN: After 5 consecutive failures, skip provider for 60s cooldown
        - HALF_OPEN: After cooldown, allow 1 test request
        
        Thread-safe using asyncio.Lock.
        """
        
        CLOSED = "closed"
        OPEN = "open" 
        HALF_OPEN = "half_open"
        
        def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 60.0):
            self._failure_threshold = failure_threshold
            self._cooldown = cooldown_seconds
            self._failures = 0
            self._state = self.CLOSED
            self._last_failure_time: float | None = None
            self._lock = asyncio.Lock()
        
        @property
        def state(self) -> str:
            return self._state
        
        async def record_success(self) -> None:
            """Reset failure count on success."""
            async with self._lock:
                self._failures = 0
                self._state = self.CLOSED
        
        async def record_failure(self) -> None:
            """Increment failure count, potentially opening circuit."""
            async with self._lock:
                self._failures += 1
                self._last_failure_time = time.monotonic()
                if self._failures >= self._failure_threshold:
                    self._state = self.OPEN
        
        async def can_execute(self) -> bool:
            """Check if request should proceed.
            
            Returns True if circuit is CLOSED or HALF_OPEN.
            Transitions OPEN -> HALF_OPEN after cooldown.
            """
            async with self._lock:
                if self._state == self.CLOSED:
                    return True
                
                if self._state == self.OPEN:
                    if self._last_failure_time and \
                       time.monotonic() - self._last_failure_time >= self._cooldown:
                        self._state = self.HALF_OPEN
                        return True
                    return False
                
                # HALF_OPEN: allow one test request
                return True
    ```

    Add globals:
    - `_host_token_buckets: dict[str, TokenBucket]`
    - `_bucket_lock: asyncio.Lock`
    - `_provider_circuits: dict[str, CircuitBreakerState]`
    - `_circuit_lock: asyncio.Lock`
  </action>
  <verify>
    <automated>python -c "from src.utils.scraping_utils import TokenBucket, CircuitBreakerState; import asyncio; tb = TokenBucket(10); cb = CircuitBreakerState(); asyncio.run(tb.acquire()); print('TokenBucket works'); print(cb.state)"</automated>
  </verify>
  <done>TokenBucket and CircuitBreakerState classes with proper asyncio.Lock protection</done>
</task>

<task type="auto">
  <name>Task 2: Update _rate_limit_host() to use TokenBucket</name>
  <files>src/utils/scraping_utils.py</files>
  <action>
    Modify `_rate_limit_host()` function (lines 334-367) to use TokenBucket.

    Changes:
    1. Get `requests_per_minute` from settings: `settings.get("rate_limit.requests_per_minute", 10.0)`
    2. Get or create per-host TokenBucket (not semaphore for rate limiting)
    3. Use existing per-host semaphore for concurrency control (keep as-is)
    4. NEW: Call `await bucket.acquire()` after acquiring semaphore

    Flow should be:
    ```
    1. Acquire per-host semaphore (concurrency limit)
    2. Acquire token from per-host TokenBucket (rate limit)
    3. Return both to caller (semaphore released after fetch)
    ```

    Note: The function signature stays the same, rate_limit param still ignored (D-08: rate limiter wraps existing function but uses config).
  </action>
  <verify>
    <automated>python -c "
import asyncio
from src.utils.scraping_utils import _rate_limit_host
async def test():
    sem = await _rate_limit_host('https://example.com')
    print(f'Semaphore acquired: {sem is not None}')
    sem.release()
asyncio.run(test())
"</automated>
  </verify>
  <done>_rate_limit_host() uses TokenBucket for time-based rate limiting, semaphore still handles concurrency</done>
</task>

<task type="auto">
  <name>Task 3: Add rate_limit config to config.yaml</name>
  <files>config.yaml</files>
  <action>
    Add rate_limit section to config.yaml (after existing sections):

    ```yaml
    # Rate limiting configuration
    rate_limit:
      requests_per_minute: 10  # Per-domain default
    ```

    This enables per-domain rate limiting without modifying provider code.
  </action>
  <verify>
    <automated>python -c "
from src.application.config import _get_settings
settings = _get_settings()
rpm = settings.get('rate_limit.requests_per_minute', 10)
print(f'Rate limit config: {rpm} req/min')
"</automated>
  </verify>
  <done>config.yaml has rate_limit.requests_per_minute setting</done>
</task>

</tasks>

<verification>
After Wave 1:
- `python -c "from src.utils.scraping_utils import TokenBucket, CircuitBreakerState; print('Imports OK')"` passes
- Rate limiter reads from config.yaml
</verification>

<success_criteria>
1. TokenBucket class uses time.monotonic() for token refill
2. TokenBucket is per-host (keyed by netloc)
3. CircuitBreakerState has CLOSED/OPEN/HALF_OPEN state machine
4. _rate_limit_host() acquires both semaphore AND TokenBucket
5. config.yaml has rate_limit.requests_per_minute setting
</success_criteria>

<output>
After completion, create `.planning/phases/04-http-resilience-rate-limiting/04-01-SUMMARY.md`
</output>
