---
status: investigating
trigger: "arxiv-embedding-slow"
created: 2026-04-03T00:00:00
updated: 2026-04-03T00:00:00
---

## Current Focus
next_action: "Document findings - issue NOT reproducible with current code"
hypothesis: "arXiv content is ~3x longer causing proportionally longer encoding time"
test: "Added diagnostic logging, ran uv run python -m src.cli --debug fetch --all multiple times"
expecting: "Confirm arXiv is 28x slower per batch"

## Symptoms
expected: 所有 feed 的 embedding batch 速度应该相近
actual: arXiv (260 articles, 9 batches) 花费 25s (2.8s/batch)，OpenAI (903 articles, 29 batches) 只花 3s (0.1s/batch)
errors: 无报错，只是慢
reproduction: uv run python -m src.cli --debug fetch --all
started: 首次观察到此问题

## Eliminated
- hypothesis: "Batch size difference causing slowdown"
  evidence: "Both feeds have similar batch sizes (~30 articles/batch). arXiv: 260/9=29, OpenAI: 903/29=31"
  timestamp: 2026-04-03

- hypothesis: "Code path difference between feed types"
  evidence: "Both use identical add_article_embeddings() function. Code path is shared."
  timestamp: 2026-04-03

- hypothesis: "arXiv encoding is 28x slower per article"
  evidence: |
    DIAGNOSTIC RUN RESULTS:
    OpenAI: 903 articles, total_chars=54977, avg=61 chars/article, encode+add=9.610s, per-article=0.011s
    arXiv: 260 articles, total_chars=45741, avg=176 chars/article, encode+add=3.532s, per-article=0.014s

    Per-article encoding: arXiv is ~27% slower, NOT 28x slower.
    Per-character encoding: arXiv is actually FASTER (13000 chars/s vs 5700 chars/s)
  timestamp: 2026-04-03

- hypothesis: "Original issue was in embedding function"
  evidence: "Cannot reproduce the issue. Current code shows similar per-article encoding times for both feeds."
  timestamp: 2026-04-03

## Evidence
- timestamp: 2026-04-03
  checked: "src/storage/vector.py add_article_embeddings function"
  found: "Both arXiv and OpenAI use the same batch embedding function via same code path."
  implication: "The difference must be in content characteristics"

- timestamp: 2026-04-03
  checked: "RSS feed content via curl"
  found: |
    arXiv abstracts are ~500-900 characters (full paper abstracts)
    OpenAI descriptions are ~100-200 characters (short blog summaries)
  implication: "arXiv content is inherently longer, but not 28x longer"

- timestamp: 2026-04-03
  checked: "DIAGNOSTIC RUN - uv run python -m src.cli --debug fetch --all (multiple runs)"
  found: |
    Run 1:
    - OpenAI: 903 articles, 54977 chars total, avg=61, encode=11.336s (0.013s/article)
    - arXiv: 260 articles, 45741 chars total, avg=176, encode=3.401s (0.013s/article)

    Run 2:
    - OpenAI: 903 articles, 54977 chars total, avg=61, encode=9.610s (0.011s/article)
    - arXiv: 260 articles, 45741 chars total, avg=176, encode=3.532s (0.014s/article)
  implication: "Per-article encoding time is nearly identical. arXiv content is ~3x longer but encodes at same rate."

- timestamp: 2026-04-03
  checked: "Per-character encoding efficiency"
  found: |
    OpenAI: 54977 chars / 9.610s = 5720 chars/s
    arXiv: 45741 chars / 3.532s = 12950 chars/s
  implication: "arXiv is actually MORE efficient per character (longer texts have better compression ratio in tokenizers)"

- timestamp: 2026-04-03
  checked: "Batch processing behavior"
  found: "add_article_embeddings is called ONCE per feed with all new articles from that feed. User reported '9 batches' for arXiv, but current code processes all 260 articles in ONE batch call."
  implication: "Either batching behavior changed, or user was measuring something different"

## Resolution
root_cause: "ISSUE NOT REPRODUCED. Current diagnostic data shows arXiv encoding is NOT 28x slower than OpenAI. Per-article encoding times are nearly identical (~0.013s). The original issue may have been: (1) a transient issue, (2) specific to certain conditions, or (3) based on incorrect measurement/assumption."
fix: "No fix needed - issue cannot be reproduced with current code"
verification: "Ran fetch --all twice, measured encoding times. arXiv: ~0.014s/article, OpenAI: ~0.011s/article. Both scale linearly with total content."
files_changed: []
---
