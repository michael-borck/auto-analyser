"""Tests for format detection."""

from pathlib import Path

import pytest

from auto_analyser.detector import detect, DetectionResult


class TestDetect:
    def test_pdf_routes_to_document_analyser(self):
        result = detect(Path("report.pdf"))
        assert result.analyser == "document-analyser"
        assert result.warning is None

    def test_mp3_routes_to_speech_analyser(self):
        result = detect(Path("recording.mp3"))
        assert result.analyser == "speech-analyser"

    def test_csv_routes_to_records_analyser(self):
        result = detect(Path("data.csv"))
        assert result.analyser == "records-analyser"

    def test_py_routes_to_code_analyser(self):
        result = detect(Path("script.py"))
        assert result.analyser == "code-analyser"

    def test_mp4_routes_to_video_analyser(self):
        result = detect(Path("lecture.mp4"))
        assert result.analyser == "video-analyser"

    def test_php_routes_to_wordpress_analyser(self):
        result = detect(Path("functions.php"))
        assert result.analyser == "wordpress-analyser"

    def test_json_has_warning(self):
        result = detect(Path("data.json"))
        assert result.analyser == "records-analyser"
        assert result.warning is not None
        assert "records-analyser" in result.warning or "document-analyser" in result.warning

    def test_ipynb_routes_to_code_analyser_with_warning(self):
        result = detect(Path("notebook.ipynb"))
        assert result.analyser == "code-analyser"
        assert result.warning is not None

    def test_html_routes_to_code_analyser(self):
        result = detect(Path("index.html"))
        assert result.analyser == "code-analyser"

    def test_unknown_extension_returns_none(self):
        result = detect(Path("file.xyz"))
        assert result.analyser is None
        assert result.warning is not None

    def test_case_insensitive(self):
        result = detect(Path("REPORT.PDF"))
        assert result.analyser == "document-analyser"
