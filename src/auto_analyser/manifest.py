"""Capability manifest for the lens family.

auto-analyser is the family's orchestrator — it routes files to the other members
rather than analysing a content type itself, so it claims no extensions and is not
auto-routable. It exposes this manifest (constant + `auto-analyser manifest`) for
symmetry with the rest of the family; it has no HTTP server of its own.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def _version() -> str:
    try:
        return version("auto-analyser")
    except PackageNotFoundError:
        return "0.0.0"


MANIFEST: dict = {
    "name": "auto-analyser",
    "version": _version(),
    "role": "orchestrator",
    "accepts": ["any file — routes to the right analyser"],
    "extensions": [],
    "auto_routable": False,
    "produces": "routed analysis",
}
