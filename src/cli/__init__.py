"""CLI package - re-exports cli() function.

Note: The cli() function is currently defined in src.cli (cli.py).
This __init__.py re-exports it using importlib to avoid circular imports.
After migration is complete (Task 8), this file will define cli directly.
"""
import importlib.util
import sys

# Explicitly load src.cli module (cli.py file, not the package)
_spec = importlib.util.spec_from_file_location("src.cli_module", "/Users/y3/radar/src/cli.py")
_module = importlib.util.module_from_spec(_spec)
sys.modules["src.cli_module"] = _module
_spec.loader.exec_module(_module)
cli = _module.cli

if __name__ == "__main__":
    cli()
