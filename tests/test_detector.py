"""Tests for format detection."""

from pathlib import Path

import pytest

from prism.detector import detect, DetectionResult


class TestDetect:
    def test_pdf_routes_to_document_lens(self):
        result = detect(Path("report.pdf"))
        assert result.lens == "document-lens"
        assert result.warning is None

    def test_mp3_routes_to_audio_lens(self):
        result = detect(Path("recording.mp3"))
        assert result.lens == "audio-lens"

    def test_csv_routes_to_data_lens(self):
        result = detect(Path("data.csv"))
        assert result.lens == "data-lens"

    def test_py_routes_to_code_lens(self):
        result = detect(Path("script.py"))
        assert result.lens == "code-lens"

    def test_mp4_routes_to_video_lens(self):
        result = detect(Path("lecture.mp4"))
        assert result.lens == "video-lens"

    def test_json_has_warning(self):
        result = detect(Path("data.json"))
        assert result.lens == "data-lens"
        assert result.warning is not None
        assert "document-lens" in result.warning or "data-lens" in result.warning

    def test_ipynb_routes_to_code_lens_with_warning(self):
        result = detect(Path("notebook.ipynb"))
        assert result.lens == "code-lens"
        assert result.warning is not None

    def test_html_routes_to_code_lens(self):
        result = detect(Path("index.html"))
        assert result.lens == "code-lens"

    def test_unknown_extension_returns_none(self):
        result = detect(Path("file.xyz"))
        assert result.lens is None
        assert result.warning is not None

    def test_case_insensitive(self):
        result = detect(Path("REPORT.PDF"))
        assert result.lens == "document-lens"
