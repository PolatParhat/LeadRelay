"""Smoke test: proves pytest can import our package from src/."""

import leadrelay


def test_package_imports():
    assert leadrelay.__doc__.startswith("LeadRelay")
