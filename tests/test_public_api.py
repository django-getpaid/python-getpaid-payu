"""Tests for the public package API."""

import tomllib
from importlib.metadata import version
from pathlib import Path

import getpaid_payu


def test_version() -> None:
    """__version__ must match the installed package metadata."""
    assert getpaid_payu.__version__ == version("python-getpaid-payu")


def test_core_dependency_floor() -> None:
    pyproject_data = tomllib.loads(Path("pyproject.toml").read_text())
    assert (
        "python-getpaid-core>=3.1.0"
        in pyproject_data["project"]["dependencies"]
    )
