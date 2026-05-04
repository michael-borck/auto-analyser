"""Tests for the Router."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poly_lens.config import FamilyConfig, LensConfig
from poly_lens.router import Router, RoutingError


def _make_config(lens_name: str, lens_type: str, **kwargs) -> FamilyConfig:
    return FamilyConfig(lenses={
        lens_name: LensConfig(type=lens_type, **kwargs)
    })


class TestRouterCLI:
    def test_cli_lens_called_with_file(self, sample_csv: Path):
        cfg = _make_config("data-lens", "cli", command="datalens")
        router = Router(config=cfg)

        fake_data = {"format": "csv", "profile": {"rows": 2}}
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(fake_data),
                stderr="",
            )
            result = router.route(sample_csv, lens_name="data-lens")

        assert "success" not in result
        assert result["format"] == "csv"
        assert result["routed_to"] == "data-lens"
        call_args = mock_run.call_args[0][0]
        assert "datalens" in call_args
        assert "analyse" in call_args
        assert str(sample_csv) in call_args

    def test_cli_failure_raises_routing_error(self, sample_csv: Path):
        cfg = _make_config("data-lens", "cli", command="datalens")
        router = Router(config=cfg)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr=json.dumps({"error": "Unsupported format"}),
            )
            with pytest.raises(RoutingError, match="Unsupported format"):
                router.route(sample_csv, lens_name="data-lens")

    def test_unknown_lens_raises_routing_error(self, sample_csv: Path):
        cfg = FamilyConfig(lenses={})
        router = Router(config=cfg)
        with pytest.raises(RoutingError, match="not configured"):
            router.route(sample_csv, lens_name="no-such-lens")


class TestRouterDetect:
    def test_csv_auto_routes_to_data_lens(self, sample_csv: Path):
        cfg = _make_config("data-lens", "cli", command="datalens")
        router = Router(config=cfg)

        fake_data = {"format": "csv", "profile": {}}
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(fake_data), stderr=""
            )
            result = router.route(sample_csv)

        assert result["routed_to"] == "data-lens"
        assert "success" not in result

    def test_unknown_format_raises_routing_error(self, tmp_path: Path):
        cfg = FamilyConfig(lenses={})
        router = Router(config=cfg)
        p = tmp_path / "file.xyz"
        p.write_bytes(b"data")
        with pytest.raises(RoutingError, match="Unknown format"):
            router.route(p)
