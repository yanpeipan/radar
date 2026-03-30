---
status: awaiting_human_verify
trigger: "RSSProvider.fetch_articles(https://deepmind.com/blog/feed/basic/) failed: Failed to perform, curl: (35) TLS connect error: error:00000000:invalid library (0):OPENSSL_internal:invalid library (0)"
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T16:20:00Z
---

## Current Focus

hypothesis: "The TLS error is caused by curl_cffi's SSL library initialization issue when connecting through an HTTP proxy to deepmind.google. The error is intermittent and usually resolved after retries."
test: "Ran multiple fetch attempts with and without proxy settings"
expecting: "If hypothesis is true: error should be intermittent and resolve with retries; using explicit proxy parameter works better than env vars"
next_action: "Request human verification from user"

## Symptoms

expected: Feed content fetched successfully via HTTPS
actual: TLS connect error - curl can't establish SSL connection
errors: `curl: (35) TLS connect error: error:00000000:invalid library (0):OPENSSL_internal:invalid library (0)` when fetching https://deepmind.com/blog/feed/basic/
reproduction: Run any fetch on a feed URL, e.g. `python -c "from src.providers import match_first; print(match_first('https://deepmind.com/blog/feed/basic/'))"`
started: Started happening now when trying to fetch deepmind feed

## Eliminated

- hypothesis: "Error is caused by verify=False being passed explicitly"
  evidence: "grep shows verify=False is not set anywhere in the codebase. The default verify=True works reliably."
  timestamp: 2026-03-30T16:10:00Z

## Evidence

- timestamp: 2026-03-30T00:00:00Z
  checked: Initial symptom report
  found: Error is curl (35) TLS connect error with OPENSSL_internal:invalid library
  implication: This is an OpenSSL library issue, not a network or URL issue

- timestamp: 2026-03-30T16:02:00Z
  checked: scrapling Fetcher.get behavior with deepmind.google
  found: "error:00000000:invalid library" occurs on first attempt(s) but request eventually succeeds after retries
  implication: The TLS error is transient and scrapling's retry mechanism handles it

- timestamp: 2026-03-30T16:03:00Z
  checked: Other HTTPS sites (example.com, google.com, news.ycombinator.com)
  found: Most HTTPS sites work without TLS errors, deepmind.google consistently shows the error
  implication: The issue might be specific to deepmind.google's TLS configuration

- timestamp: 2026-03-30T16:05:00Z
  checked: curl_cffi bundled SSL libraries
  found: curl_cffi ships its own libssl.3.dylib and libcurl-impersonate.4.dylib in .dylibs folder
  implication: The bundled SSL library might have initialization issues with certain TLS handshakes

- timestamp: 2026-03-30T16:10:00Z
  checked: "verify=False" vs "verify=True" behavior
  found: "verify=False" causes intermittent TLS errors with deepmind.google; "verify=True" (default) works reliably
  implication: The issue is specifically with SSL verification disabled in curl_cffi, not a general TLS issue

- timestamp: 2026-03-30T16:12:00Z
  checked: Proxy environment variable behavior
  found: With HTTP proxy env vars set, requests to deepmind.google fail intermittently with TLS errors; without proxy, requests succeed
  implication: The issue is related to how curl_cffi handles TLS through an HTTP proxy

- timestamp: 2026-03-30T16:12:42Z
  checked: Explicit proxy parameter vs environment variable
  found: Passing proxy explicitly as `proxies={'https': proxy, 'http': proxy}` works better than relying on environment variables
  implication: curl_cffi may have a bug with reading proxy from environment variables

## Resolution

root_cause: "curl_cffi (used by scrapling) has an intermittent TLS initialization issue when connecting to deepmind.google through an HTTP proxy. The bundled OpenSSL library in curl_cffi sometimes fails to initialize properly for TLS connections through a proxy, causing error 35. The issue is transient and usually resolves after 2-3 retries. The default retries (3) may not be enough in some cases."
fix: "Increased default retries from 3 to 5, increased retry_delay from 1s to 2s, and added explicit timeout of 30s to handle intermittent TLS errors more gracefully."
verification: "Verified by testing fetch_articles with deepmind.google feed - returned 100 articles successfully. All 22 provider tests pass."
files_changed: ["src/providers/rss_provider.py"]