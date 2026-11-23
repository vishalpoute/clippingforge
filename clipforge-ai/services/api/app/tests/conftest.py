import sys, os
# Add the parent directory (services/api) to sys.path so that 'import app' works for tests
package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if package_root not in sys.path:
    sys.path.insert(0, package_root)
