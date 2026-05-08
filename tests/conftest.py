"""Shared fixtures for auto-analyser tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "sample.csv"
    p.write_text("name,value\nAlice,1\nBob,2\n")
    return p
