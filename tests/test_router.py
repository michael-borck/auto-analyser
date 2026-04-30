"""Tests for the Router."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prism.config import FamilyConfig, LensConfig
from prism.router import Router


def _make_config(lens_name: str, lens_type: str, **kwargs) -> FamilyConfig:
    return FamilyConfig(lenses={
        lens_name: LensConfig(type=lens_type, **kwargs)
    })


class TestRouterCLI:
    def test_cli_lens_called_with_file(self, sample_csv: Path):
        cfg = _make_config("data-lens", "cli", command="data-lens")
        router = Router(config=cfg)

        fake_result = {"success": True, "data": {"format": "csv", "profile": {"rows": 2}}}
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(fake_result),
                stderr="",
            )
            result = router.route(sample_csv, lens_name="data-lens")

        assert result["success"] is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "data-lens" in call_args
        assert "analyse" in call_args
        assert str(sample_csv) in call_args

    def test_unknown_lens_returns_error(self, sample_csv: Path):
        cfg = FamilyConfig(lenses={})
        router = Router(config=cfg)
        result = router.route(sample_csv, lens_name="no-such-lens")
        assert result["success"] is False
        assert "not configured" in result["error"]


class TestRouterDetect:
    def test_csv_auto_routes_to_data_lens(self, sample_csv: Path):
        cfg = _make_config("data-lens", "cli", command="data-lens")
        router = Router(config=cfg)

        fake_result = {"success": True, "data": {}}
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(fake_result), stderr=""
            )
            result = router.route(sample_csv)

        assert result["success"] is True
        assert result.get("routed_to") == "data-lens"

    def test_unknown_format_returns_error(self, tmp_path: Path):
        cfg = FamilyConfig(lenses={})
        router = Router(config=cfg)
        p = tmp_path / "file.xyz"
        p.write_bytes(b"data")
        result = router.route(p)
        assert result["success"] is False
        assert "Unknown format" in result["error"]
