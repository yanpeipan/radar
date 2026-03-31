# Release Process

This project uses **GitHub Actions + trusted publishing** for PyPI releases. No manual token handling required.

## Release Steps

### 1. Bump Version

Update `version` in `pyproject.toml`:

```toml
[project]
version = "1.1.0"
```

### 2. Commit & Tag

```bash
# Commit all changes
git add -A && git commit -m "Release v1.1.0"

# Create tag
git tag -a v1.1.0 -m "Release v1.1.0"

# Push (triggers CI)
git push && git push origin v1.1.0
```

### 3. Create GitHub Release

```bash
gh release create v1.1.0 \
  --title "v1.1.0" \
  --notes "## Changes\n- ..."
```

Publishing a GitHub release (with tag) automatically triggers the `Release to PyPI` workflow.

### 4. Verify

- **PyPI**: https://pypi.org/project/feedship/
- **GitHub**: https://github.com/yanpeipan/feedship/releases

## CI/CD Details

**Trigger**: GitHub release published (not release *created* — must be *published*)

**Workflow** (`.github/workflows/release.yml`):
1. Checkout `${{ github.ref }}` (the tag)
2. Build with `python -m build`
3. Publish via `pypa/gh-action-pypi-publish@release/v1` using OIDC trusted publishing

**Requirements**:
- PyPI project with [trusted publishing](https://docs.pypi.org/trusted-publishers/) configured
- GitHub Actions environment `pypi` linked to PyPI project
- `id-token: write` permission for OIDC token exchange

## Manual Build (Optional)

```bash
# Clean build
rm -rf dist/ build/ *.egg-info

# Build
python -m build

# Verify
ls dist/
```

Manual build artifacts can be uploaded with `twine upload dist/*` if needed.

## Rollback

If a release fails or has issues:

```bash
# Delete the GitHub release
gh release delete v1.1.0 --yes

# Delete local and remote tags
git tag -d v1.1.0
git push origin --delete v1.1.0

# Fix code, then re-release starting from step 1
```
