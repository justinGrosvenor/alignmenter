"""Basic smoke tests for scaffold."""

from alignmenter import app


def test_cli_app_exists() -> None:
    assert app is not None
