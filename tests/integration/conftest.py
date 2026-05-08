"""Pytest configuration for integration tests."""

import pytest


@pytest.fixture(autouse=True)
def _no_repology_rate_limit(monkeypatch):
    """Disable the Repology rate limiter so tests don't sleep."""
    import windowstolinux.resolver.repology as rep
    monkeypatch.setattr(rep, "_MIN_REQUEST_INTERVAL", 0.0)
