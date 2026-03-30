# Pre-Release Checklist for radar

## Version & Metadata

- [ ] Bump version in `pyproject.toml` (currently `1.0.0`)
- [ ] Update `pyproject.toml` description if needed
- [ ] Verify `pyproject.toml` `[project.scripts]` entry is `radar` (currently `rss-reader`)
- [ ] Update README.md version badge if applicable
- [ ] Add CHANGELOG.md or update version history

## Code Quality

- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Check test coverage: `pytest --cov=src --cov-report=term-missing`
- [ ] Verify no `TODO`, `FIXME`, or `XXX` comments left in code
- [ ] Check for hardcoded paths or secrets
- [ ] Verify all dependencies are listed in `pyproject.toml`
- [ ] Run linting if configured (flake8, ruff, mypy)

## Documentation

- [ ] Update README.md with latest features
- [ ] Verify all doc links are working
- [ ] Add installation instructions for common platforms
- [ ] Document optional dependencies (`[ml]`, `[cloudflare]`)
- [ ] Add troubleshooting section if needed

## Package Build

- [ ] Install build tools: `pip install build twine`
- [ ] Clean previous builds: `rm -rf dist/ build/ *.egg-info`
- [ ] Build package: `python -m build`
- [ ] Verify `dist/` contains `.whl` and `.tar.gz`
- [ ] Test installation from local dist: `pip install dist/rss-reader-*.whl`

## PyPI Publishing

- [ ] Create PyPI account if not exists
- [ ] Add PyPI token to environment (e.g., `PYPI_TOKEN`)
- [ ] Upload to TestPyPI first: `twine upload --repository testpypi dist/*`
- [ ] Verify test installation: `pip install --index-url https://test.pypi.org/simple/ radar`
- [ ] Upload to PyPI: `twine upload dist/*`
- [ ] Verify live: `pip install radar`

## Git & Release

- [ ] Create git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
- [ ] Push tag: `git push origin v1.0.0`
- [ ] Create GitHub Release with changelog
- [ ] Enable GitHub Actions for automated testing if not done

## Post-Release

- [ ] Verify pip install works on clean environment
- [ ] Test basic commands: `radar --help`, `radar feed --help`
- [ ] Announce release if applicable
