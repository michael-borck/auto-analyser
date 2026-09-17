"""Tests for multi-rule cascades and the explicit-only heuristics.

The document rules (provenance always; conversation/reflection when the
content heuristics fire) are tolerance-first: a heuristic false positive
costs one extra labelled signal set, never a failure.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from auto_analyser.config import AnalyserConfig, FamilyConfig
from auto_analyser.heuristics import chat_likeness, journal_likeness
from auto_analyser.router import Router


def _doc_router(tmp_path: Path, **cfg_extra) -> tuple[Router, Path]:
    config = FamilyConfig(
        analysers={
            "document-analyser": AnalyserConfig(
                type="http", url="http://localhost:8000"
            ),
            "provenance-analyser": AnalyserConfig(
                type="http", url="http://localhost:8014"
            ),
            "conversation-analyser": AnalyserConfig(
                type="http", url="http://localhost:8009"
            ),
            "reflection-analyser": AnalyserConfig(
                type="http", url="http://localhost:8015"
            ),
        },
        **cfg_extra,
    )
    doc = tmp_path / "essay.docx"
    doc.write_bytes(b"PK fake-but-suffix-is-what-matters")
    return Router(config=config), doc


def _mock_document(text: str, fmt: str = "docx") -> None:
    respx.post("http://localhost:8000/analyse").mock(
        return_value=httpx.Response(
            200,
            json={"format": fmt, "file_path": "", "text": text},
        )
    )


CHAT_TEXT = (
    "# ChatGPT conversation\n"
    "User: Explain recursion please\n"
    "Assistant: Sure — recursion is a function that calls itself.\n"
    "User: Can you show an example?\n"
    "Assistant: def f(n): return 1 if n < 2 else n * f(n-1)\n"
)
ESSAY_TEXT = (
    "The Industrial Revolution reshaped European economies. "
    "Factories concentrated labour and capital in urban centres. "
) * 12  # long enough to judge, but third-person and non-reflective
JOURNAL_TEXT = (
    "# Reflective journal, week 3\n"
    "I learned more from the failed prototype than from the final build. "
    "I struggled with the state machine at first, and I felt out of my depth. "
    "Next time I would sketch the transitions before writing any code. "
    "Looking back, my understanding of immutability was superficial. "
    "I noticed I kept avoiding the type checker, and I think that cost me hours. "
    "I realised the tests I skipped were exactly the ones that would have caught "
    "the bug, and I found it much harder to debug without them. I felt frustrated "
    "on Tuesday when the build broke again, but I think the debugging session "
    "taught me more than the lectures did. Going forward I need to write the "
    "tests first and treat them as part of the design, not an afterthought. "
    "In hindsight, my plan was optimistic and I should have budgeted time for "
    "the integration work. I took away a simple rule: small commits, tested often."
)


# ── heuristics: chat_likeness ────────────────────────────────────────────


def test_chat_likeness_role_markers():
    assert chat_likeness({"text": CHAT_TEXT, "file_path": "notes.docx"})


def test_chat_likeness_folder_convention():
    assert chat_likeness(
        {
            "text": "hello there friend",
            "file_path": "submissions/a/chat/transcript.docx",
        }
    )


def test_chat_likeness_filename_needs_corroboration():
    assert chat_likeness(
        {"text": "chat about weather\nYou: hi\n", "file_path": "mychat.docx"}
    )
    assert not chat_likeness(
        {"text": "a plain essay with the word chat in it", "file_path": "mychat.docx"}
    )


def test_chat_likeness_negative():
    assert not chat_likeness({"text": ESSAY_TEXT, "file_path": "essay.docx"})
    assert not chat_likeness({"text": "", "file_path": "chat.docx"})


# ── heuristics: journal_likeness ─────────────────────────────────────────


def test_journal_likeness_cues():
    assert journal_likeness({"text": JOURNAL_TEXT, "file_path": "week3.docx"})


def test_journal_likeness_filename():
    assert journal_likeness({"text": "short", "file_path": "reflective-journal.docx"})


def test_journal_likeness_negative_on_third_person_essay():
    assert not journal_likeness({"text": ESSAY_TEXT, "file_path": "essay.docx"})


def test_journal_likeness_short_thin_doc_never_fires():
    assert not journal_likeness(
        {
            "text": "I learned. Next time I will plan. I felt good. I noticed growth.",
            "file_path": "x.docx",
        }
    )


# ── multi-cascade wiring ─────────────────────────────────────────────────


@respx.mock
def test_document_cascades_to_provenance_and_conversation(tmp_path: Path):
    router, doc = _doc_router(tmp_path)
    _mock_document(CHAT_TEXT)
    prov = respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(
            200, json={"creator_app": "Word", "total_editing_time_minutes": 12}
        )
    )
    conv = respx.post("http://localhost:8009/analyse").mock(
        return_value=httpx.Response(200, json={"analytics": {"turn_count": 4}})
    )
    refl = respx.post("http://localhost:8015/analyse").mock(
        return_value=httpx.Response(200, json={"should": "not be called"})
    )

    result = router.route(doc, analyser_name="document-analyser")

    assert result["routed_to"] == "document-analyser"
    routed = [b["routed_to"] for b in result["cascades"]]
    assert routed == [
        "provenance-analyser",
        "conversation-analyser",
    ]  # reflection didn't match
    assert prov.called and conv.called and not refl.called
    # Legacy singular key still present (first match).
    assert result["cascade"]["routed_to"] == "provenance-analyser"
    # Heuristic cascades are labelled with their trigger.
    assert result["cascades"][1]["triggered_by"] == "document-analyser.heuristic"


@respx.mock
def test_document_cascades_to_provenance_only_for_plain_essay(tmp_path: Path):
    router, doc = _doc_router(tmp_path)
    _mock_document(ESSAY_TEXT)
    respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(200, json={"creator_app": "Word"})
    )
    conv = respx.post("http://localhost:8009/analyse").mock(
        return_value=httpx.Response(200, json={})
    )
    refl = respx.post("http://localhost:8015/analyse").mock(
        return_value=httpx.Response(200, json={})
    )

    result = router.route(doc, analyser_name="document-analyser")

    assert [b["routed_to"] for b in result["cascades"]] == ["provenance-analyser"]
    assert not conv.called and not refl.called


@respx.mock
def test_provenance_cascade_skipped_for_unsupported_formats(tmp_path: Path):
    """Provenance reads office metadata only — .txt/.md never cascade there."""
    router, doc = _doc_router(tmp_path)
    _mock_document("plain notes", fmt="txt")
    prov = respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(200, json={})
    )

    result = router.route(doc, analyser_name="document-analyser")

    assert "cascades" not in result and "cascade" not in result
    assert not prov.called


@respx.mock
def test_cascades_config_gate_disables_heuristics(tmp_path: Path):
    router, doc = _doc_router(tmp_path, cascades_enabled=False)
    _mock_document(CHAT_TEXT)

    result = router.route(doc, analyser_name="document-analyser")

    assert "cascades" not in result and "cascade" not in result


@respx.mock
def test_explicit_cascade_true_overrides_config_gate(tmp_path: Path):
    router, doc = _doc_router(tmp_path, cascades_enabled=False)
    _mock_document(CHAT_TEXT)
    respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(200, json={})
    )

    result = router.route(doc, analyser_name="document-analyser", cascade=True)

    assert "cascades" in result


@respx.mock
def test_cascade_failure_recorded_and_others_still_run(tmp_path: Path):
    router, doc = _doc_router(tmp_path)
    _mock_document(CHAT_TEXT)
    respx.post("http://localhost:8014/analyse").mock(
        return_value=httpx.Response(500, text="boom")
    )
    conv = respx.post("http://localhost:8009/analyse").mock(
        return_value=httpx.Response(200, json={"analytics": {"turn_count": 4}})
    )

    result = router.route(doc, analyser_name="document-analyser")

    assert "error" in result["cascades"][0]
    assert "500" in result["cascades"][0]["error"]
    assert conv.called  # later rules unaffected by an earlier failure
