"""Tests for the cascade routing rule (image-analyser → diagram-analyser).

The rule fires when image-analyser's response carries `diagram.is_diagram = True`.
The cascade is best-effort: failures attach `cascade.error` instead of raising,
so the primary result is always preserved.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from auto_analyser.config import AnalyserConfig, FamilyConfig
from auto_analyser.router import Router, RoutingError


def _make_router(tmp_path: Path) -> tuple[Router, Path]:
    """Router with image-analyser + diagram-analyser both HTTP-dispatched."""
    config = FamilyConfig(analysers={
        "image-analyser": AnalyserConfig(type="http", url="http://localhost:8006"),
        "diagram-analyser": AnalyserConfig(type="http", url="http://localhost:8013"),
    })
    png = tmp_path / "flow.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake-but-suffix-is-what-matters")
    return Router(config=config), png


# ── cascade fires when is_diagram=True ───────────────────────────────────


@respx.mock
def test_cascade_fires_when_is_diagram_true(tmp_path: Path):
    router, png = _make_router(tmp_path)
    respx.post("http://localhost:8006/analyse").mock(
        return_value=httpx.Response(
            200,
            json={
                "format": "PNG",
                "diagram": {
                    "is_diagram": True,
                    "confidence": 0.94,
                    "backend": "heuristic",
                },
            },
        )
    )
    diag_route = respx.post("http://localhost:8013/analyse").mock(
        return_value=httpx.Response(
            200,
            json={
                "file_format": "image",
                "diagram_type": "flowchart",
                "graph": {"node_count": 3, "edge_count": 2},
            },
        )
    )

    result = router.route(png, analyser_name="image-analyser")

    # Primary preserved.
    assert result["routed_to"] == "image-analyser"
    assert result["format"] == "PNG"
    # Cascade attached and ran.
    assert "cascade" in result
    casc = result["cascade"]
    assert casc["routed_to"] == "diagram-analyser"
    assert casc["triggered_by"] == "image-analyser.diagram.is_diagram"
    assert "error" not in casc
    assert casc["result"]["diagram_type"] == "flowchart"
    assert diag_route.called


# ── cascade does NOT fire when is_diagram=False ──────────────────────────


@respx.mock
def test_cascade_skipped_when_is_diagram_false(tmp_path: Path):
    router, png = _make_router(tmp_path)
    respx.post("http://localhost:8006/analyse").mock(
        return_value=httpx.Response(
            200,
            json={"format": "PNG", "diagram": {"is_diagram": False, "confidence": 0.1, "backend": "heuristic"}},
        )
    )
    diag_route = respx.post("http://localhost:8013/analyse").mock(
        return_value=httpx.Response(200, json={"diagram_type": "should-not-be-called"})
    )

    result = router.route(png, analyser_name="image-analyser")

    assert "cascade" not in result
    assert not diag_route.called


# ── cascade=False disables it explicitly ────────────────────────────────


@respx.mock
def test_cascade_can_be_disabled_per_call(tmp_path: Path):
    router, png = _make_router(tmp_path)
    respx.post("http://localhost:8006/analyse").mock(
        return_value=httpx.Response(
            200,
            json={"format": "PNG", "diagram": {"is_diagram": True, "confidence": 0.9, "backend": "heuristic"}},
        )
    )
    diag_route = respx.post("http://localhost:8013/analyse").mock(
        return_value=httpx.Response(200, json={"diagram_type": "flowchart"})
    )

    result = router.route(png, analyser_name="image-analyser", cascade=False)

    assert "cascade" not in result
    assert not diag_route.called


# ── cascade failure is recorded, primary still succeeds ──────────────────


@respx.mock
def test_cascade_target_unreachable_records_error_not_raises(tmp_path: Path):
    router, png = _make_router(tmp_path)
    respx.post("http://localhost:8006/analyse").mock(
        return_value=httpx.Response(
            200,
            json={"format": "PNG", "diagram": {"is_diagram": True, "confidence": 0.9, "backend": "heuristic"}},
        )
    )
    # diagram-analyser endpoint returns 500.
    respx.post("http://localhost:8013/analyse").mock(
        return_value=httpx.Response(500, text="server crashed")
    )

    result = router.route(png, analyser_name="image-analyser")

    # Primary still succeeded.
    assert result["routed_to"] == "image-analyser"
    # Cascade was attempted; the error is reported, not raised.
    assert "cascade" in result
    assert "error" in result["cascade"]
    assert "500" in result["cascade"]["error"] or "server crashed" in result["cascade"]["error"]


# ── cascade target not configured (e.g. user-trimmed config) ─────────────


@respx.mock
def test_cascade_target_not_configured_records_error(tmp_path: Path):
    """If diagram-analyser isn't in the config at all, surface a clear error in cascade."""
    config = FamilyConfig(analysers={
        "image-analyser": AnalyserConfig(type="http", url="http://localhost:8006"),
    })
    png = tmp_path / "x.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    router = Router(config=config)

    respx.post("http://localhost:8006/analyse").mock(
        return_value=httpx.Response(
            200,
            json={"format": "PNG", "diagram": {"is_diagram": True, "confidence": 0.9, "backend": "heuristic"}},
        )
    )

    result = router.route(png, analyser_name="image-analyser")

    assert "cascade" in result
    assert "not configured" in result["cascade"]["error"]


# ── cascade does not fire for non-image primaries ────────────────────────


@respx.mock
def test_cascade_does_not_fire_for_other_primaries(tmp_path: Path):
    """Cascade rule is keyed on the primary analyser name, so this guards against accidental triggering."""
    config = FamilyConfig(analysers={
        "records-analyser": AnalyserConfig(type="http", url="http://localhost:8003"),
        "diagram-analyser": AnalyserConfig(type="http", url="http://localhost:8013"),
    })
    csv = tmp_path / "data.csv"
    csv.write_text("a,b\n1,2\n")
    router = Router(config=config)

    respx.post("http://localhost:8003/analyse").mock(
        return_value=httpx.Response(
            200,
            json={"format": "csv", "diagram": {"is_diagram": True}},  # rogue field — should be ignored
        )
    )
    diag_route = respx.post("http://localhost:8013/analyse").mock(
        return_value=httpx.Response(200, json={})
    )

    result = router.route(csv, analyser_name="records-analyser")
    assert "cascade" not in result
    assert not diag_route.called


# ── disabled-by-default constructor param ────────────────────────────────


@respx.mock
def test_router_cascade_default_off(tmp_path: Path):
    router, png = _make_router(tmp_path)
    router._cascade_default = False  # equivalent to Router(..., cascade=False)
    respx.post("http://localhost:8006/analyse").mock(
        return_value=httpx.Response(
            200,
            json={"format": "PNG", "diagram": {"is_diagram": True, "confidence": 0.9, "backend": "heuristic"}},
        )
    )

    result = router.route(png, analyser_name="image-analyser")
    assert "cascade" not in result
