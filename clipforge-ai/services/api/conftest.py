"""Isolate test databases and relative media paths before importing the app."""
import os
import sys
import tempfile
from pathlib import Path

_api = Path(__file__).resolve().parent
sys.path.insert(0, str(_api))
_sandbox = tempfile.TemporaryDirectory(prefix="clipforge-tests-", ignore_cleanup_errors=True)
_original_dir = Path.cwd()
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_sandbox.name) / "test.db").as_posix()
os.chdir(_sandbox.name)


def pytest_unconfigure(config):
    from app.db import engine
    engine.dispose()
    os.chdir(_original_dir)
    _sandbox.cleanup()

def pytest_configure(config):
    if config.option.basetemp is None:
        config.option.basetemp = str(Path(_sandbox.name) / "fixtures")
