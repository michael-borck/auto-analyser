"""Capability manifest for the lens family (built via lens-contract).

auto-analyser is the family's orchestrator — it routes files to the other members
rather than analysing a content type itself, so it claims no extensions and is not
auto-routable. It exposes the manifest (constant, `auto-analyser manifest`, and
`GET /manifest`) and a routing `POST /analyse` for symmetry with the rest of the
family.
"""
from __future__ import annotations

from lens_contract import make_manifest

MANIFEST = make_manifest(
    name="auto-analyser",
    role="orchestrator",
    accepts=["any file — routes to the right analyser"],
    extensions=[],
    auto_routable=False,
    produces="routed analysis",
)
