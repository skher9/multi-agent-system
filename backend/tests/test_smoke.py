"""Smoke test: proves the test runner works and the right Python is in use."""

import sys


def test_python_version_is_312() -> None:
    assert sys.version_info[:2] == (3, 12)
