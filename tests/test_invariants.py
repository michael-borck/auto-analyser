"""Invariant tests — fast, no real dispatch, run by default.

For auto-analyser specifically: there is no /health endpoint and no
package __version__ to drift on. The invariants here guard the
detector-vs-config registration mismatch (a route that points to an
analyser name not in the default config) and the public symbol
imports.
"""

from pathlib import Path

import pytest


def test_package_imports_cleanly() -> None:
    """The package and all its public surfaces must import.

    Smoke alarm — guards packaging bugs and circular imports.
    """
    import auto_analyser  # noqa: F401
    from auto_analyser.cli import main  # noqa: F401
    from auto_analyser.router import Router, RoutingError  # noqa: F401
    from auto_analyser.detector import detect, DetectionResult  # noqa: F401
    from auto_analyser.config import load_config, FamilyConfig, AnalyserConfig  # noqa: F401


def test_every_detected_analyser_has_a_default_config() -> None:
    """Detector routes and config defaults must stay in sync.

    If someone adds a new file extension that routes to e.g. 'kotlin-analyser'
    without also adding 'kotlin-analyser' to config._DEFAULTS, the router
    will reject every dispatch. This test catches that drift the moment
    the rename or addition lands.
    """
    from auto_analyser.detector import _ROUTES
    from auto_analyser.config import _DEFAULTS

    detected_analyser_names = set(_ROUTES.values()) - {None}
    configured_analyser_names = set(_DEFAULTS.keys())

    missing = detected_analyser_names - configured_analyser_names
    assert not missing, (
        f"Detector routes to {missing} but no entries exist in config._DEFAULTS. "
        f"Either add the analyser to _DEFAULTS or remove the route from _ROUTES."
    )


def test_router_dispatch_to_unknown_analyser_raises_loudly(tmp_path: Path) -> None:
    """Dispatch must raise RoutingError, not silently no-op or return None."""
    from auto_analyser.config import AnalyserConfig, FamilyConfig
    from auto_analyser.router import Router, RoutingError

    config = FamilyConfig(analysers={
        "records-analyser": AnalyserConfig(type="cli", command="records-analyser", formats=[".csv"]),
    })
    router = Router(config=config)

    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b\n1,2\n")

    with pytest.raises(RoutingError, match="not configured"):
        router.route(csv_file, analyser_name="kotlin-analyser")
