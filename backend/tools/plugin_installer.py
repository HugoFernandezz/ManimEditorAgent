"""Install a Manim plugin package and verify it imports correctly."""
from __future__ import annotations
import subprocess
import importlib
import sys


def install_plugin(package_name: str) -> dict[str, str]:
    """pip-install a package and check it imports. Returns status dict."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package_name, "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"status": "failed", "error": result.stderr.strip()}

    # Best-effort import check — package name != import name in some cases
    import_name = package_name.replace("-", "_").split("[")[0]
    try:
        importlib.import_module(import_name)
        return {"status": "installed"}
    except ImportError:
        # Package installed but import name differs — still treat as OK
        return {"status": "installed", "note": f"installed but import as '{import_name}' failed — may need different import name"}
