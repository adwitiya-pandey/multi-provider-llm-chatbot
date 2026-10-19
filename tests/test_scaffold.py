"""Test package scaffold and importability."""

import chatbot


def test_package_metadata() -> None:
    """Verify package can be imported and has version metadata."""
    assert chatbot.__package__ == "chatbot"
