"""Canonical worker identity helpers shared by Paper A analysis stages."""

from __future__ import annotations

from typing import Any


def normalize_worker_id(value: Any) -> str:
    """Return the canonical numeric worker id for W-prefixed/padded inputs."""
    text = str(value or "").strip()
    if text[:1].lower() == "w" and text[1:].isdigit():
        text = text[1:]
    if text.isdigit():
        return str(int(text))
    return text
