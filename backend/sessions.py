"""Manages per-video Anthropic client instances.

Each video gets an isolated client so no conversation history leaks between runs.
"""
from __future__ import annotations
import anthropic


def new_client() -> anthropic.Anthropic:
    """Return a fresh SDK client — one per video."""
    return anthropic.Anthropic()
