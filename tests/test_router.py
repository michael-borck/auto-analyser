"""Tests for the Router."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from auto_analyser.config import FamilyConfig, AnalyserConfig
from auto_analyser.router import Router, RoutingError


def _make_config(analyser_name: str, analyser_type: str, **kwargs) -> FamilyConfig:
    return FamilyConfig(analysers={
        analyser_name: AnalyserConfig(type=analyser_type, **kwargs)
    })


class TestRouterCLI:
    def test_cli_analyser_called_with_file(self, sample_csv: Path):
        cfg = _make_config("records-analyser", "cli", command="records-analyser")
        router = Router(config=cfg)

        fake_data = {"format": "csv", "profile": {"rows": 2}}
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(fake_data),
                stderr="",
            )
            result = router.route(sample_csv, analyser_name="records-analyser")

        assert result["format"] == "csv"
        assert result["routed_to"] == "records-analyser"
        call_args = mock_run.call_args[0][0]
        assert "records-analyser" in call_args
        assert str(sample_csv) in call_args

    def test_cli_failure_raises_routing_error(self, sample_csv: Path):
        cfg = _make_config("records-analyser", "cli", command="records-analyser")
        router = Router(config=cfg)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr=json.dumps({"error": "Unsupported format"}),
            )
            with pytest.raises(RoutingError, match="Unsupported format"):
                router.route(sample_csv, analyser_name="records-analyser")

    def test_unknown_analyser_raises_routing_error(self, sample_csv: Path):
        cfg = FamilyConfig(analysers={})
        router = Router(config=cfg)
        with pytest.raises(RoutingError, match="not configured"):
            router.route(sample_csv, analyser_name="no-such-analyser")


class TestRouterDetect:
    def test_csv_auto_routes_to_records_analyser(self, sample_csv: Path):
        cfg = _make_config("records-analyser", "cli", command="records-analyser")
        router = Router(config=cfg)

        fake_data = {"format": "csv", "profile": {}}
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(fake_data), stderr=""
            )
            result = router.route(sample_csv)

        assert result["routed_to"] == "records-analyser"

    def test_unknown_format_raises_routing_error(self, tmp_path: Path):
        cfg = FamilyConfig(analysers={})
        router = Router(config=cfg)
        p = tmp_path / "file.xyz"
        p.write_bytes(b"data")
        with pytest.raises(RoutingError, match="Unknown format"):
            router.route(p)
