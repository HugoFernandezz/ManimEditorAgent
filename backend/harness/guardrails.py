"""Structured validation of agent outputs.

Without guardrails, an LLM returning malformed JSON crashes the pipeline.
Each guardrail returns a (valid, parsed_or_error) tuple — never raises.
"""
from __future__ import annotations
import json
import re
from typing import Any


class GuardrailViolation(Exception):
    """Raised when a guardrail explicitly fails after all repair attempts."""


def extract_json_array(raw: str) -> tuple[bool, Any]:
    """Find the first JSON array in `raw`. Tolerant of preamble/postamble."""
    raw = raw.strip()
    if not raw:
        return False, "empty response"
    # Strip markdown fences
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return False, "no JSON array found"
    try:
        return True, json.loads(raw[start:end + 1])
    except json.JSONDecodeError as e:
        return False, f"json decode error: {e}"


def extract_json_object(raw: str) -> tuple[bool, Any]:
    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return False, "no JSON object found"
    try:
        return True, json.loads(raw[start:end + 1])
    except json.JSONDecodeError as e:
        return False, f"json decode error: {e}"


def extract_yaml_block(raw: str) -> tuple[bool, str]:
    """Extract content inside ```yaml ... ``` fences."""
    m = re.search(r"```yaml\s*\n([\s\S]*?)\n```", raw)
    if not m:
        return False, "no yaml block found"
    return True, m.group(1)


def python_code_well_formed(code: str) -> tuple[bool, str]:
    """Quick syntactic check on agent-produced Python."""
    import ast
    try:
        ast.parse(code)
        if "class Scene" not in code and not re.search(r"class\s+\w+\s*\(", code):
            return False, "no Scene class defined"
        return True, "ok"
    except SyntaxError as e:
        return False, f"syntax error line {e.lineno}: {e.msg}"


def plugins_proposal_valid(parsed: Any) -> tuple[bool, str]:
    if not isinstance(parsed, list):
        return False, "expected a list"
    for i, p in enumerate(parsed):
        if not isinstance(p, dict):
            return False, f"item {i} is not an object"
        for key in ("name", "description"):
            if key not in p:
                return False, f"item {i} missing key '{key}'"
        if not isinstance(p["name"], str) or not p["name"]:
            return False, f"item {i} has empty name"
    return True, "ok"


def qa_report_valid(yaml_text: str) -> tuple[bool, str]:
    """Best-effort check; we don't fully parse YAML (no extra dep)."""
    if "status:" not in yaml_text:
        return False, "missing status field"
    if "needs_fix" not in yaml_text and "ok" not in yaml_text:
        return False, "status must be 'ok' or 'needs_fix'"
    return True, "ok"
