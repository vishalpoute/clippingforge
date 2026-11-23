import os, sys
# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.dirname(__file__))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
# Add the FastAPI app package path so `import app.xxx` works
_app_path = os.path.join(_repo_root, 'services', 'api', 'app')
if _app_path not in sys.path:
    sys.path.insert(0, _app_path)
# Make this directory a package
__all__ = []
