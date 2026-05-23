"""Build the plugin-context string injected into Planner and Coder prompts.

Joins the Researcher's proposal (which carries description/relevance) with the
install results (which carry success/failure). Only plugins that were both
approved AND successfully installed show up — failed installs are noise to the
downstream agents.
"""
from __future__ import annotations
from typing import Any


_NO_PLUGINS = (
    "No external plugins were approved for this video. "
    "Use only `manim` (Community Edition) itself — do not import anything else."
)


def build_plugin_context(manifest: dict[str, Any]) -> str:
    """Return a markdown bullet list suitable for inclusion in an agent prompt.

    Returns a fallback sentence when nothing usable is available — never empty,
    so prompts stay grammatical regardless of the manifest state.
    """
    install_results: dict[str, dict] = manifest.get("plugins") or {}
    proposal: list[dict] = manifest.get("plugins_proposal") or []

    by_name = {p.get("name"): p for p in proposal if isinstance(p, dict) and p.get("name")}

    usable: list[dict] = []
    for name, result in install_results.items():
        if not isinstance(result, dict) or result.get("status") != "installed":
            continue
        meta = by_name.get(name, {})
        usable.append({
            "name": name,
            "description": (meta.get("description") or "").strip(),
            "relevance":   (meta.get("relevance")   or "").strip(),
        })

    if not usable:
        return _NO_PLUGINS

    lines = [
        "APPROVED PLUGINS (already pip-installed — you may import and use them):",
    ]
    for p in usable:
        desc = p["description"] or "(no description)"
        when = f" Use it when: {p['relevance']}" if p["relevance"] else ""
        lines.append(f"- `{p['name']}`: {desc}.{when}")
    lines.append(
        "Prefer these over custom implementations when relevant. "
        "Do not import packages NOT in this list."
    )
    return "\n".join(lines)
