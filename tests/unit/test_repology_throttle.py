"""Unit tests for the Repology rate-limiter (_throttle)."""

from __future__ import annotations

import time

import pytest

import windowstolinux.resolver.repology as rep


@pytest.fixture(autouse=True)
def _reset_throttle_state(monkeypatch):
    """Each test gets a clean rate-limit state and interval."""
    monkeypatch.setattr(rep, "_last_request_at", 0.0)
    # _no_repology_rate_limit in conftest sets _MIN_REQUEST_INTERVAL=0 for
    # most tests; individual tests that need a real interval restore it.


def test_throttle_no_sleep_when_first_call(mocker) -> None:
    mock_sleep = mocker.patch("windowstolinux.resolver.repology.time.sleep")
    rep._MIN_REQUEST_INTERVAL = 1.0
    rep._last_request_at = 0.0  # far in the past

    rep._throttle()

    mock_sleep.assert_not_called()


def test_throttle_sleeps_when_called_immediately_after_previous(mocker, monkeypatch) -> None:
    mock_sleep = mocker.patch("windowstolinux.resolver.repology.time.sleep")
    monkeypatch.setattr(rep, "_MIN_REQUEST_INTERVAL", 1.0)
    monkeypatch.setattr(rep, "_last_request_at", time.monotonic())  # just now

    rep._throttle()

    mock_sleep.assert_called_once()
    wait = mock_sleep.call_args[0][0]
    assert 0 < wait <= 1.0


def test_throttle_sleep_duration_is_remaining_interval(mocker, monkeypatch) -> None:
    mock_sleep = mocker.patch("windowstolinux.resolver.repology.time.sleep")
    monkeypatch.setattr(rep, "_MIN_REQUEST_INTERVAL", 2.0)
    # Pretend 0.5s elapsed since last request
    monkeypatch.setattr(rep, "_last_request_at", time.monotonic() - 0.5)

    rep._throttle()

    wait = mock_sleep.call_args[0][0]
    assert 1.3 < wait < 1.6  # roughly 1.5s remaining


def test_throttle_updates_last_request_at(monkeypatch) -> None:
    monkeypatch.setattr(rep, "_MIN_REQUEST_INTERVAL", 0.0)
    monkeypatch.setattr(rep, "_last_request_at", 0.0)

    before = time.monotonic()
    rep._throttle()
    after = time.monotonic()

    assert before <= rep._last_request_at <= after


def test_throttle_no_sleep_when_interval_is_zero(mocker, monkeypatch) -> None:
    mock_sleep = mocker.patch("windowstolinux.resolver.repology.time.sleep")
    monkeypatch.setattr(rep, "_MIN_REQUEST_INTERVAL", 0.0)
    monkeypatch.setattr(rep, "_last_request_at", time.monotonic())

    rep._throttle()

    mock_sleep.assert_not_called()
