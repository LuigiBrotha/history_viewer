import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BLOCKED_IMPORT = """
import importlib.abc
import sys

BLOCKED = {"shapely", "numpy", "scipy"}


class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError(f"blocked: {name}")
        return None


sys.meta_path.insert(0, Blocker())
import app.main
loaded = BLOCKED & set(sys.modules)
assert not loaded, loaded
"""


def test_importing_the_app_does_not_need_the_routing_dependencies():
    result = subprocess.run(
        [sys.executable, "-c", BLOCKED_IMPORT],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 0, result.stderr
