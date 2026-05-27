"""HTTP-surface tests for the preset feature — GET /presets and POST /analyse?preset=…"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_preset_targets(monkeypatch):
    """Build an app whose Router knows about the preset members (HTTP-dispatched)."""
    from auto_analyser import api as api_module
    from auto_analyser.config import AnalyserConfig, FamilyConfig
    from auto_analyser.router import Router

    config = FamilyConfig(analysers={
        "document-analyser":   AnalyserConfig(type="http", url="http://localhost:8000"),
        "provenance-analyser": AnalyserConfig(type="http", url="http://localhost:8014"),
        "revision-analyser":   AnalyserConfig(type="http", url="http://localhost:8016"),
        "reflection-analyser": AnalyserConfig(type="http", url="http://localhost:8015"),
    })
    monkeypatch.setattr(api_module, "_router", Router(config=config))
    return TestClient(api_module.app)


def test_get_presets_lists_all(app_with_preset_targets):
    r = app_with_preset_targets.get("/presets")
    assert r.status_code == 200
    body = r.json()
    assert "authentic-essay" in body["presets"]
    assert body["presets"]["authentic-essay"] == [
        "document-analyser",
        "provenance-analyser",
        "revision-analyser",
        "reflection-analyser",
    ]


@respx.mock
def test_analyse_with_preset_runs_bundle(app_with_preset_targets, tmp_path: Path):
    # All four configured members respond OK; one emits a flag.
    respx.post("http://localhost:8000/analyse").mock(
        return_value=httpx.Response(200, json={"word_count": 1500})
    )
    respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(200, json={"flags": ["edit_time_low_for_size"]})
    )
    respx.post("http://localhost:8016/analyse").mock(
        return_value=httpx.Response(200, json={"paste_burst_count": 0, "flags": []})
    )
    respx.post("http://localhost:8015/analyse").mock(
        return_value=httpx.Response(200, json={"depth_band": "critical", "flags": []})
    )

    r = app_with_preset_targets.post(
        "/analyse?preset=authentic-essay",
        files={"file": ("essay.docx", b"x", "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["preset"] == "authentic-essay"
    assert len(body["members"]) == 4
    assert "provenance-analyser:edit_time_low_for_size" in body["flags_across_bundle"]


def test_unknown_preset_returns_400(app_with_preset_targets):
    r = app_with_preset_targets.post(
        "/analyse?preset=garbage",
        files={"file": ("essay.docx", b"x", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "Unknown preset" in r.json()["detail"]
