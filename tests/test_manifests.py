"""Tests for manifest-driven routing."""

from pathlib import Path

import httpx

from auto_analyser import manifests
from auto_analyser.config import AnalyserConfig, FamilyConfig
from auto_analyser.detector import detect, resolve_routes


def test_build_routes_from_manifests(monkeypatch):
    config = FamilyConfig(
        analysers={
            "document-analyser": AnalyserConfig(type="http", url="http://x:8000"),
            "conversation-analyser": AnalyserConfig(type="cli", command="conversation-analyser"),
        }
    )
    fakes = {
        "http": {"name": "document-analyser", "extensions": [".pdf", ".docx"], "auto_routable": True},
        "cli": {"name": "conversation-analyser", "extensions": [], "auto_routable": False},
    }
    monkeypatch.setattr(manifests, "fetch_manifest", lambda cfg, **k: fakes[cfg.type])

    routes = manifests.build_routes(config)
    assert routes[".pdf"] == "document-analyser"
    assert routes[".docx"] == "document-analyser"
    # auto_routable=False (explicit-only lens) is never routed
    assert "conversation-analyser" not in routes.values()


def test_fetch_manifest_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(httpx, "get", boom)
    cfg = AnalyserConfig(type="http", url="http://x:8000")
    assert manifests.fetch_manifest(cfg) is None


def test_resolve_routes_falls_back_to_static(monkeypatch):
    monkeypatch.setattr("auto_analyser.manifests.build_routes", lambda cfg: {})
    routes = resolve_routes(FamilyConfig(analysers={}))
    assert routes[".pdf"] == "document-analyser"  # from the static fallback


def test_detect_uses_provided_routes():
    routes = {".conv": "conversation-analyser"}
    assert detect(Path("x.conv"), routes=routes).analyser == "conversation-analyser"
    assert detect(Path("x.pdf"), routes=routes).analyser is None  # not in provided table
