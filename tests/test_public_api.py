"""Canonical public surface (see lens-analysers/CONVENTIONS.md).

auto-analyser is an orchestrator: it exposes ``Router`` (aliased ``AutoAnalyser``),
a module-level ``analyse()`` router call, ``MANIFEST`` and ``__version__``.
"""

from __future__ import annotations

import auto_analyser


def test_canonical_surface_importable():
    from auto_analyser import (  # noqa: F401
        MANIFEST,
        AutoAnalyser,
        Router,
        analyse,
    )

    assert callable(analyse)
    assert AutoAnalyser is Router
    assert MANIFEST["name"] == "auto-analyser"
    assert isinstance(auto_analyser.__version__, str)


def test_surface_in_dunder_all():
    for name in ("Router", "AutoAnalyser", "analyse", "MANIFEST", "__version__"):
        assert name in auto_analyser.__all__
