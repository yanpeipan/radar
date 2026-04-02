# Release Process

This project uses **GitHub Actions + trusted publishing** for PyPI releases. No manual token handling required.

## Release Checklist

**Every time before releasing, run this exact sequence:**

```bash
# 0. Confirm versions (MUST do this first!)
CURRENT=$(curl -s https://pypi.org/pypi/feedship/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")
echo "Current PyPI version: $CURRENT"
echo "What version do you want to release? (e.g., 1.2.3)"
# If CURRENT is already the version you want, NO need to release!

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
version = "X.Y.Z"  # <- change to your release version
```

### 2. Commit and Push

```bash
# Push the commit FIRST (so the tag points to a pushed commit)
git add -A && git commit -m "Release vX.Y.Z"
git push
```

### 3. Create GitHub Release

```bash
# gh release create handles the tag — DO NOT run git push --tags separately
gh release create vX.Y.Z \
  --title "vX.Y.Z" \
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
# Expected: Latest: X.Y.Z
```

## CI/CD Pipeline

**Trigger**: GitHub release *published* (draft releases do NOT trigger CI)

**Workflow** (`.github/workflows/release.yml`):

1. `actions/checkout@v4` with `ref: ${{ github.ref }}` — checks out the tag
2. **Version validation** — verifies pyproject.toml version matches tag (fails fast)
3. `python -m build` — builds sdist + wheel
4. `pypa/gh-action-pypi-publish@release/v1` — publishes via OIDC trusted publishing (with 30s retry)
5. **Concurrency control** — `cancel-in-progress: true` prevents double-release races

**Key safety features:**
- `concurrency` block prevents parallel release runs
- Version pre-flight check prevents HTTP 400 from mismatch
- Built-in retry (30s) handles transient PyPI failures
- `timeout-minutes: 10` prevents infinite hangs

## Common Failures

### "HTTP 400 Bad Request" on PyPI upload
- **Cause**: pyproject.toml version didn't match the tag version
- **Prevention**: The CI now validates this before building

### Release workflow didn't trigger
- **Cause**: Used `git tag && git push --tags` instead of `gh release create`
- **Prevention**: Always use `gh release create` — it creates both tag AND GitHub Release

### Lint fails on GitHub but passes locally
- **Cause**: pre-commit ruff version differs from `uv run ruff` version
- **Prevention**: Keep `.pre-commit-config.yaml` ruff rev synchronized

### "File already exists" on PyPI
- **Cause**: Released the same version twice (or a retry raced with the original)
- **Fix**: Bump version in pyproject.toml, then re-release
- **Prevention**: `concurrency` block now cancels in-progress runs

### Build succeeds but PyPI publish fails transiently
- **Cause**: Network hiccup or PyPI temporary overload
- **Fix**: Re-trigger the workflow from GitHub Actions UI — the build is already done and PyPI will accept the same file
- **Prevention**: `retry-time-seconds: 30` handles most transient failures

## Rollback

```bash
# 1. Delete GitHub release
gh release delete vX.Y.Z --yes

# 2. Delete local and remote tags
git tag -d vX.Y.Z
git push origin --delete vX.Y.Z

# 3. Fix code, update version in pyproject.toml, then re-release from step 1
```
