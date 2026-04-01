# Release Process

This project uses **GitHub Actions + trusted publishing** for PyPI releases. No manual token handling required.

## Release Checklist

**Every time before releasing, run this exact sequence:**

```bash
# 1. Ensure working tree is COMPLETELY clean
git status --short
# If any files show (M, A, D, ??), commit or stash them first

# 2. Run lint + format with pre-commit (this is what GitHub CI runs)
uv run pre-commit run --all

# 3. Verify version in pyproject.toml matches expected release version
grep 'version = ' pyproject.toml
# e.g., for v1.2.2 release, output should be: version = "1.2.2"

# 4. Build locally to catch any issues
rm -rf dist/ build/ *.egg-info
python -m build

# 5. Verify build produces correct version
unzip -p dist/*.whl '*.dist-info/METADATA' 2>/dev/null | grep '^Version:'
```

## Release Steps

### 1. Bump Version (CRITICAL - do this first!)

```bash
# Edit pyproject.toml line 3
version = "1.2.2"  # <- change to your release version
```

### 2. Commit

```bash
git add -A && git commit -m "Release v1.2.2"
```

### 3. Create GitHub Release

```bash
gh release create v1.2.2 \
  --title "v1.2.2" \
  --notes "## Changes\n- ..."
```

**This is the only command that creates both a tag AND a GitHub Release, which triggers the PyPI publish workflow.**

### 4. Verify

```bash
# Check GitHub Actions (takes ~1 min)
gh run list --limit 3

# Check PyPI (takes ~2 min to update)
curl -s https://pypi.org/pypi/feedship/json | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Latest:', d['info']['version'])
"
# Expected: Latest: 1.2.2
```

## CI/CD Pipeline

**Trigger**: GitHub release *published* (draft releases do NOT trigger CI)

**Workflow** (`.github/workflows/release.yml`):
1. `actions/checkout@v4` with `ref: ${{ github.ref }}` — checks out the tag
2. `python -m build` — builds sdist + wheel
3. `pypa/gh-action-pypi-publish@release/v1` — publishes via OIDC trusted publishing

**Key requirement**: `ref: ${{ github.ref }}` ensures CI builds from the tag, not master.

## Common Failures

### "HTTP 400 Bad Request" on PyPI upload
- **Cause**: pyproject.toml version didn't match the tag version (e.g., released v1.2.2 but pyproject.toml still had v1.2.1)
- **Prevention**: Always verify version in pyproject.toml matches expected release version before step 3

### Release workflow didn't trigger
- **Cause**: Used `git tag && git push --tags` instead of `gh release create`
- **Prevention**: Always use `gh release create` — it creates both tag AND GitHub Release

### Lint fails on GitHub but passes locally
- **Cause**: pre-commit ruff version (v0.6.4) differs from `uv run ruff` version (v0.15.8)
- **Prevention**: Keep `.pre-commit-config.yaml` ruff rev synchronized with `pyproject.toml` dependencies

### "File already exists" on PyPI
- **Cause**: Version was already published to PyPI
- **Fix**: Bump version in pyproject.toml, then re-release

## Rollback

```bash
# 1. Delete GitHub release
gh release delete v1.2.2 --yes

# 2. Delete local and remote tags
git tag -d v1.2.2
git push origin --delete v1.2.2

# 3. Fix code, update version in pyproject.toml, then re-release from step 1
```
