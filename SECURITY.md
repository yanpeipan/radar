# Security Policy

## Supported Versions

The following versions of feedship receive security updates:

| Version | Supported          | Notes                                    |
| ------- | ------------------ | ---------------------------------------- |
| 1.7.x   | :white_check_mark: | Current stable release                   |
| < 1.7   | :x:                | No longer actively maintained            |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

**Please do not report security vulnerabilities through public GitHub Issues.**

Instead, please report them via one of the following methods:

1. **GitHub Private Vulnerability Reporting** (preferred)
   - Navigate to the [Security tab](https://github.com/Y3cco/feedship/security/advisories/new) on the repository
   - Click "Report a vulnerability"
   - Provide as much detail as possible about the affected code and how to reproduce it

2. **Email** (alternative)
   - Contact the maintainers directly through GitHub

### What to Include

When reporting a vulnerability, please include:

- Description of the vulnerability
- Steps to reproduce the issue
- Affected versions (if known)
- Potential impact assessment
- Any suggested mitigations or fixes (optional)

### Response Timeline

- **Acknowledgment**: Within 48 hours of report
- **Initial assessment**: Within 7 days
- **Fix timeline**: Depends on severity; critical issues prioritized

## Known CVEs and Tracking

feedship uses automated tools to track and address known vulnerabilities in its dependencies:

### CVE Scanning (CI)

- [anchore/grype](https://github.com/anchore/grype) runs on every pull request and push to `main`
- Scans `pyproject.toml` against the live Grype vulnerability database
- **Fails CI on medium and higher severity CVEs** (`--fail-on medium`)
- Gryke database is updated on every scan (`GRYPE_DB_UPDATE_MODE=always`)

### Pinned / Constrained Dependencies

The following CVE-prone packages have upper-version bounds in `pyproject.toml` to prevent automatic upgrades to vulnerable versions:

| Package                | Constraint         | CVE Concern                                          |
| ---------------------- | ------------------ | ---------------------------------------------------- |
| `feedparser`           | `< 7`              | XML entity expansion / billion-laughs attacks        |
| `trafilatura`           | `< 1.11`           | Path traversal in HTML parsing                       |
| `chromadb`              | `< 1.0`            | Authentication bypass, information disclosure        |
| `sentence-transformers`| `< 4.0`            | Model loading from untrusted sources                 |
| `httpx`                 | `< 0.29.0`         | SSRF vulnerabilities                                 |
| `lxml`                  | `< 7.0.0`          | Historic XML parsing CVEs                           |
| `pyyaml`                | `< 6.0.4`          | Code execution (CVE-2022-28463)                      |
| `jinja2`                | `< 3.1.7`          | Path traversal (CVE-2025-27516)                      |

### Automated Dependency Updates

[Dependabot](.github/dependabot.yml) monitors the project weekly for:

- **Python package updates** (pip ecosystem) — via `pyproject.toml`
- **GitHub Actions updates** — for CI/CD workflows

Security patches (minor/patch updates for production dependencies) are auto-merged without manual review. Dependabot PRs are labeled `security` and `dependencies` for easy filtering.

### Transitive Dependencies

Some vulnerabilities may exist in transitive dependencies that cannot be directly pinned (e.g., packages that are dependencies of pinned packages). These are tracked by:

- Grype CI scans (covers all transitive deps)
- Dependabot automated PRs (updates indirect dependencies)
- Manual review when Dependabot creates security-related PRs

## Security Best Practices for Users

- **Keep feedship updated**: Run `pip install --upgrade feedship` regularly
- **Network isolation**: Run feedship in a sandboxed environment since it fetches content from external URLs
- **Feed sources**: Only add trusted RSS feeds and websites to your subscription list
- **API keys**: Store API keys in environment variables or `config.yaml`, never commit them to version control

## Scope

feedship is a local-only personal资讯系统. It does not expose a network server or API by default. Security concerns related to the following are out of scope for this project:

- Vulnerabilities in third-party websites scraped via feedship
- Denial-of-service attacks against upstream RSS feeds or websites
- User-added malicious feed sources (user responsibility)
