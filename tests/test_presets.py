"""Tests for the named preset bundles (parallel-composition counterpart to cascade rules).

The presets defined in router._PRESETS map names to lists of family members to
invoke on the same file. A preset call:

- Never raises on per-member failure — failed members report {"error": "..."}.
- Reports unconfigured members the same way (not an exception).
- Flattens each member's `flags` list into a top-level `flags_across_bundle`
  prefixed by the member name.
- Raises RoutingError only for input-level problems (unknown preset, missing file).
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from auto_analyser.config import AnalyserConfig, FamilyConfig
from auto_analyser.router import Router, RoutingError, list_presets


# ── list_presets / module API ────────────────────────────────────────────


class TestListPresets:
    def test_returns_all_v1_presets(self):
        presets = list_presets()
        # v1 set per ASSESSMENT-MAP.md
        assert set(presets) == {
            "skill-with-evidence",
            "authentic-essay",
            "design-with-rationale",
            "multimedia-evidence",
            "reflective-practice",
        }

    def test_authentic_essay_members(self):
        presets = list_presets()
        assert presets["authentic-essay"] == [
            "document-analyser",
            "provenance-analyser",
            "revision-analyser",
            "reflection-analyser",
        ]

    def test_returns_copy_not_internal_ref(self):
        # Caller mutation must not affect the internal _PRESETS dict.
        presets = list_presets()
        presets["junk"] = ["nothing"]
        assert "junk" not in list_presets()


# ── input validation ─────────────────────────────────────────────────────


class TestPresetValidation:
    def test_unknown_preset_raises(self, tmp_path: Path):
        f = tmp_path / "x.docx"
        f.write_bytes(b"x")
        router = Router(config=FamilyConfig(analysers={}))
        with pytest.raises(RoutingError, match="Unknown preset"):
            router.run_preset("nonsense", f)

    def test_missing_file_raises(self, tmp_path: Path):
        router = Router(config=FamilyConfig(analysers={}))
        with pytest.raises(RoutingError, match="not found"):
            router.run_preset("authentic-essay", tmp_path / "nope.docx")


# ── run_preset behaviour ─────────────────────────────────────────────────


def _docx_fixture(tmp_path: Path, name: str = "essay.docx") -> Path:
    """A non-empty file whose suffix the preset members will accept (or not)."""
    p = tmp_path / name
    p.write_bytes(b"\x50\x4b\x03\x04fake-but-suffix-is-what-matters")
    return p


@respx.mock
def test_preset_invokes_every_configured_member(tmp_path: Path):
    """authentic-essay should call all 4 configured members on the same file."""
    f = _docx_fixture(tmp_path)
    config = FamilyConfig(analysers={
        "document-analyser":   AnalyserConfig(type="http", url="http://localhost:8000"),
        "provenance-analyser": AnalyserConfig(type="http", url="http://localhost:8014"),
        "revision-analyser":   AnalyserConfig(type="http", url="http://localhost:8016"),
        "reflection-analyser": AnalyserConfig(type="http", url="http://localhost:8015"),
    })
    router = Router(config=config)

    d_route = respx.post("http://localhost:8000/analyse").mock(
        return_value=httpx.Response(200, json={"word_count": 1500, "flags": []})
    )
    p_route = respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(200, json={"total_editing_time_minutes": 15, "flags": ["edit_time_low_for_size"]})
    )
    r_route = respx.post("http://localhost:8016/analyse").mock(
        return_value=httpx.Response(200, json={"paste_burst_count": 1, "flags": ["paste_burst_present"]})
    )
    rf_route = respx.post("http://localhost:8015/analyse").mock(
        return_value=httpx.Response(200, json={"depth_band": "descriptive", "flags": []})
    )

    result = router.run_preset("authentic-essay", f)

    assert d_route.called and p_route.called and r_route.called and rf_route.called
    assert result["preset"] == "authentic-essay"
    assert set(result["members"]) == {
        "document-analyser", "provenance-analyser",
        "revision-analyser", "reflection-analyser",
    }
    assert result["members"]["document-analyser"]["word_count"] == 1500
    # Flags from all members get flattened with member-name prefix.
    assert "provenance-analyser:edit_time_low_for_size" in result["flags_across_bundle"]
    assert "revision-analyser:paste_burst_present" in result["flags_across_bundle"]


def test_unconfigured_member_reports_error_not_raises(tmp_path: Path):
    """A preset whose member isn't in the config should report 'not configured', not crash."""
    f = _docx_fixture(tmp_path)
    # Empty config — no members at all
    router = Router(config=FamilyConfig(analysers={}))

    result = router.run_preset("authentic-essay", f)

    assert result["preset"] == "authentic-essay"
    for member in ("document-analyser", "provenance-analyser",
                   "revision-analyser", "reflection-analyser"):
        assert result["members"][member]["error"] == "not configured"
    assert result["flags_across_bundle"] == []


@respx.mock
def test_member_http_failure_reports_error_continues(tmp_path: Path):
    """An HTTP 500 from one member shouldn't fail the whole preset."""
    f = _docx_fixture(tmp_path)
    config = FamilyConfig(analysers={
        "document-analyser":   AnalyserConfig(type="http", url="http://localhost:8000"),
        "provenance-analyser": AnalyserConfig(type="http", url="http://localhost:8014"),
        "revision-analyser":   AnalyserConfig(type="http", url="http://localhost:8016"),
        "reflection-analyser": AnalyserConfig(type="http", url="http://localhost:8015"),
    })
    router = Router(config=config)

    respx.post("http://localhost:8000/analyse").mock(
        return_value=httpx.Response(200, json={"word_count": 500, "flags": []})
    )
    respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(500, text="server crashed")
    )
    respx.post("http://localhost:8016/analyse").mock(
        return_value=httpx.Response(200, json={"flags": []})
    )
    respx.post("http://localhost:8015/analyse").mock(
        return_value=httpx.Response(200, json={"flags": []})
    )

    result = router.run_preset("authentic-essay", f)

    assert "error" in result["members"]["provenance-analyser"]
    assert "500" in result["members"]["provenance-analyser"]["error"]
    # Other three succeeded.
    assert "error" not in result["members"]["document-analyser"]
    assert "error" not in result["members"]["revision-analyser"]
    assert "error" not in result["members"]["reflection-analyser"]


@respx.mock
def test_member_400_unsupported_format_reports_continues(tmp_path: Path):
    """Common case: design-with-rationale lists both diagram + site; one will report
    'unsupported format' for any given input. Both errors must record, not raise."""
    f = _docx_fixture(tmp_path)
    config = FamilyConfig(analysers={
        "diagram-analyser":    AnalyserConfig(type="http", url="http://localhost:8013"),
        "site-analyser":       AnalyserConfig(type="http", url="http://localhost:8012"),
        "provenance-analyser": AnalyserConfig(type="http", url="http://localhost:8014"),
        "reflection-analyser": AnalyserConfig(type="http", url="http://localhost:8015"),
    })
    router = Router(config=config)

    # Both diagram and site reject this input as unsupported.
    respx.post("http://localhost:8013/analyse").mock(
        return_value=httpx.Response(400, json={"detail": "Unsupported extension: .docx"})
    )
    respx.post("http://localhost:8012/analyse").mock(
        return_value=httpx.Response(400, json={"detail": "Exactly one of url or path must be supplied"})
    )
    respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(200, json={"flags": []})
    )
    respx.post("http://localhost:8015/analyse").mock(
        return_value=httpx.Response(200, json={"flags": []})
    )

    result = router.run_preset("design-with-rationale", f)

    # Two members succeed, two report errors — bundle still returns successfully.
    assert "error" in result["members"]["diagram-analyser"]
    assert "error" in result["members"]["site-analyser"]
    assert "error" not in result["members"]["provenance-analyser"]
    assert "error" not in result["members"]["reflection-analyser"]


@respx.mock
def test_flags_flattened_with_member_prefix(tmp_path: Path):
    """Flags from individual members appear in flags_across_bundle with `member:flag` prefix."""
    f = _docx_fixture(tmp_path)
    config = FamilyConfig(analysers={
        "provenance-analyser": AnalyserConfig(type="http", url="http://localhost:8014"),
        "revision-analyser":   AnalyserConfig(type="http", url="http://localhost:8016"),
        "document-analyser":   AnalyserConfig(type="http", url="http://localhost:8000"),
        "reflection-analyser": AnalyserConfig(type="http", url="http://localhost:8015"),
    })
    router = Router(config=config)

    respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(200, json={"flags": ["edit_time_low_for_size", "ai_generation_marker"]})
    )
    respx.post("http://localhost:8016/analyse").mock(
        return_value=httpx.Response(200, json={"flags": ["paste_burst_present"]})
    )
    respx.post("http://localhost:8000/analyse").mock(return_value=httpx.Response(200, json={}))
    respx.post("http://localhost:8015/analyse").mock(return_value=httpx.Response(200, json={}))

    result = router.run_preset("authentic-essay", f)

    assert "provenance-analyser:edit_time_low_for_size" in result["flags_across_bundle"]
    assert "provenance-analyser:ai_generation_marker" in result["flags_across_bundle"]
    assert "revision-analyser:paste_burst_present" in result["flags_across_bundle"]
    assert len(result["flags_across_bundle"]) == 3


@respx.mock
def test_member_with_no_flags_field_doesnt_crash(tmp_path: Path):
    """A member whose result has no `flags` key should just contribute zero flags."""
    f = _docx_fixture(tmp_path)
    config = FamilyConfig(analysers={
        "document-analyser":   AnalyserConfig(type="http", url="http://localhost:8000"),
        "provenance-analyser": AnalyserConfig(type="http", url="http://localhost:8014"),
        "revision-analyser":   AnalyserConfig(type="http", url="http://localhost:8016"),
        "reflection-analyser": AnalyserConfig(type="http", url="http://localhost:8015"),
    })
    router = Router(config=config)

    # Realistic shape — document-analyser doesn't currently emit `flags`.
    respx.post("http://localhost:8000/analyse").mock(
        return_value=httpx.Response(200, json={"word_count": 100, "readability": {}})
    )
    for url in ("http://localhost:8014/analyse",
                "http://localhost:8016/analyse",
                "http://localhost:8015/analyse"):
        respx.post(url).mock(return_value=httpx.Response(200, json={"flags": []}))

    result = router.run_preset("authentic-essay", f)
    assert result["flags_across_bundle"] == []
    assert result["members"]["document-analyser"]["word_count"] == 100
