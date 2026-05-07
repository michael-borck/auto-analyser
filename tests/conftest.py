"""Shared fixtures for auto-analyser tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    p = tmp_path / "sample.txt"
    p.write_text("This is a test document with some content.")
    return p


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "sample.csv"
    p.write_text("name,value\nAlice,1\nBob,2\n")
    return p
