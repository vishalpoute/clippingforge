import pathlib, sys

# Repository root (one level up from this shim)
_repo_root = pathlib.Path(__file__).resolve().parents[1]
# Ensure repository root is on sys.path for absolute imports
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Path to the actual FastAPI app package
_app_path = _repo_root / 'services' / 'api' / 'app'
# Point this shim package's __path__ to the real package directory
__path__ = [str(_app_path)]
