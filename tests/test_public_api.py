"""Tests for the public package API."""

import getpaid_payu


def test_version() -> None:
    assert getpaid_payu.__version__ == "3.0.0a4"
