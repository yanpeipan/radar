# Profiling Guide

This guide covers profiling tools available for identifying performance bottlenecks in feedship operations.

## Quick Start

```bash
# Enable cProfile for a fetch
feedship fetch --all --profile

# View profile results
ls profiles/
```

## cProfile (Built-in Profiling)

When `--profile` is enabled, cProfile data is saved to `profiles/fetch_<timestamp>.prof`.

**Reading the output:**
- `cumulative` time = total time in function including subcalls
- `tottime` = time excluding subcalls

**View profile data with pstats:**

```python
import pstats
stats = pstats.Stats("profiles/fetch_20240101_120000.prof")
stats.sort_stats("cumulative")
stats.print_stats(20)  # Top 20 functions
```

**Generate call graph:**

```bash
python -c "
import pstats
from pstats import SortKey
stats = pstats.Stats('profiles/fetch_*.prof')
stats.sort_stats(SortKey.CUMULATIVE)
stats.print_callers(30)
"
```

## py-spy (Production Profiling)

For lower-overhead production profiling without code changes:

```bash
# Install py-spy
pip install py-spy

# Profile a running process
py-spy record -o profile.svg --pid <PID>

# Profile and see top functions in real-time
py-spy top -- python -m src.cli fetch --all

# Profile specific duration then view flamegraph
py-spy record -o profile.svg --duration 30 -- python -m src.cli fetch --all
```

**py-spy output formats:**
- `profile.svg` - Flame graph (view in browser)
- `profile.txt` - Text summary

## Identifying Bottlenecks

**Common feedship bottlenecks:**

| Bottleneck | Symptoms | Tools |
|------------|----------|-------|
| Rate limiting convoy | 20+ seconds for fetch | cProfile + py-spy |
| N+1 queries | Many small DB calls | sqlite3 trace |
| Network I/O | HTTP requests dominate time | cProfile |
| HTML parsing | trafilatura/feedparser slow | py-spy |

**Example workflow:**

```bash
# 1. Baseline timing
time feedship fetch --all

# 2. Profile with cProfile
feedship fetch --all --profile

# 3. Analyze with py-spy for lower overhead
py-spy record -o profile.svg -- python -m src.cli fetch --all
```

## Directory Structure

```
profiles/              # cProfile .prof files
  fetch_20240101_120000.prof
  fetch_20240102_090000.prof
```

## Profile Analysis Tips

1. **Look for functions with high cumulative time** - these indicate where most time is spent
2. **Check function call counts** - high counts may indicate N+1 patterns
3. **Compare profiles before/after changes** to verify improvements
4. **Use py-spy for production** to minimize overhead
