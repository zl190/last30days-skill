"""Shared pytest fixtures for last30days tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def project_root():
    """Path to the repository root."""
    return Path(__file__).parent.parent


@pytest.fixture
def fixtures_dir(project_root):
    """Path to the fixtures directory."""
    return project_root / "fixtures"


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Temporary directory for config file tests. Auto-cleaned by pytest."""
    return tmp_path


@pytest.fixture
def load_fixture(fixtures_dir):
    """Load a JSON fixture file by name."""
    def _load(name):
        with open(fixtures_dir / name) as f:
            return json.load(f)
    return _load
