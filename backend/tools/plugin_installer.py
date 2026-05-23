"""Install a Manim plugin package and verify it imports correctly."""
from __future__ import annotations
import subprocess
import importlib
import sys
from importlib import metadata


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
        return {"status": "installed",
                "note": f"installed but import as '{import_name}' failed"}


def ensure_installed(package_name: str, extras: str | None = None) -> dict[str, str]:
    """Idempotent install — no-op if `package_name` is already importable.

    Used for system-critical plugins the pipeline pulls in by itself
    (e.g. manim-voiceover). Returns a status dict in the same shape as
    install_plugin: {"status": "installed" | "already" | "failed", ...}.
    """
    try:
        version = metadata.version(package_name)
        return {"status": "already", "version": version}
    except metadata.PackageNotFoundError:
        pass
    spec = f"{package_name}[{extras}]" if extras else package_name
    return install_plugin(spec)
