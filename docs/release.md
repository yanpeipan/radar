# Release Process

This project uses **GitHub Actions + trusted publishing** for PyPI releases. No manual token handling required.

## Release Checklist

Before each release, verify:

```bash
# 1. Tests pass
python -m pytest tests/ -x -q

# 2. Build succeeds locally
rm -rf dist/ build/ *.egg-info
python -m build

# 3. Version is correct
grep 'version = ' pyproject.toml
```

## Release Steps

### 1. Update Version

```bash
# Edit pyproject.toml
version = "1.2.0"
```

### 2. Commit & Tag

```bash
git add -A && git commit -m "Release v1.2.0"
git tag -a v1.2.0 -m "Release v1.2.0"
git push && git push origin v1.2.0
```

### 3. Create GitHub Release

```bash
gh release create v1.2.0 \
  --title "v1.2.0" \
  --notes "## Changes\n- ..."
```

Publishing the GitHub release automatically triggers `Release to PyPI` workflow.

### 4. Verify

```bash
# Check PyPI (takes ~1 min to update)
curl -s https://pypi.org/pypi/feedship/json | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Latest:', d['info']['version'])
print('Releases:', list(d['releases'].keys()))
"
```

Expected output: `Latest: 1.2.0`

## CI/CD Pipeline

**Trigger**: GitHub release published (must *publish*, not just create)

**Workflow** (`.github/workflows/release.yml`):
1. `actions/checkout@v4` with `ref: ${{ github.ref }}` — checks out the tag
2. `python -m build` — builds sdist + wheel
3. `pypa/gh-action-pypi-publish@release/v1` — publishes via OIDC trusted publishing

**Key requirement**: `ref: ${{ github.ref }}` ensures CI builds from the tag, not `master`.

## Troubleshooting

### "HTTP 400 Bad Request" on PyPI upload
- Cause: CI checked out `master` instead of the tag, building wrong version
- Fix: Ensure `release.yml` has `ref: ${{ github.ref }}`

### "File already exists" on PyPI
- Cause: Version was already published
- Fix: Bump version in `pyproject.toml`, re-tag and re-release

### Release workflow didn't trigger
- Cause: Release not *published* (only drafted)
- Fix: Click "Publish release" on GitHub

### Local build fails with `long_description` error
- Cause: Setuptools version mismatch with PEP 621 `long_description` field
- Fix: Omit `long_description` field; CI builds succeed (only warns, doesn't fail)

## Rollback

```bash
# 1. Delete GitHub release
gh release delete v1.2.0 --yes

# 2. Delete tags
git tag -d v1.2.0
git push origin --delete v1.2.0

# 3. Fix code, then re-release from step 1
```
