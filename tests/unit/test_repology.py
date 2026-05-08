"""Unit tests for windowstolinux.resolver.repology."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from windowstolinux.resolver.repology import RELEVANT_REPOS, _extract_bin_name, lookup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDOWSTOLINUX_CACHE_PATH", str(tmp_path / "cache.db"))


def _make_http_response(json_data=None, status_code: int = 200, raise_for: Exception | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("not json")
    if raise_for:
        resp.raise_for_status.side_effect = raise_for
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# _extract_bin_name
# ---------------------------------------------------------------------------


def test_extract_bin_name_finds_relevant_repo() -> None:
    data = [
        {"repo": "debian_12", "binname": "vlc", "srcname": "vlc"},
        {"repo": "ubuntu_24_04", "binname": "vlc", "srcname": "vlc"},
    ]
    assert _extract_bin_name(data) == "vlc"


def test_extract_bin_name_returns_none_for_irrelevant_repos() -> None:
    data = [{"repo": "arch", "binname": "vlc"}]
    assert _extract_bin_name(data) is None


def test_extract_bin_name_returns_none_for_empty_list() -> None:
    assert _extract_bin_name([]) is None


def test_extract_bin_name_skips_entry_without_binname() -> None:
    data = [
        {"repo": "ubuntu_24_04", "binname": "", "srcname": "vlc"},
        {"repo": "ubuntu_24_10", "binname": "vlc"},
    ]
    assert _extract_bin_name(data) == "vlc"


@pytest.mark.parametrize("repo", sorted(RELEVANT_REPOS))
def test_extract_bin_name_accepts_all_relevant_repos(repo: str) -> None:
    data = [{"repo": repo, "binname": "test-pkg"}]
    assert _extract_bin_name(data) == "test-pkg"


# ---------------------------------------------------------------------------
# lookup - cache hit
# ---------------------------------------------------------------------------


def test_lookup_returns_cached_value_without_http(mocker) -> None:
    mock_http = mocker.patch("windowstolinux.resolver.repology.httpx.get")

    from windowstolinux.resolver import cache
    cache.set("repology:vlc", "vlc")

    result = lookup("vlc")

    assert result == "vlc"
    mock_http.assert_not_called()


def test_lookup_cached_sentinel_returns_none(mocker) -> None:
    mocker.patch("windowstolinux.resolver.repology.httpx.get")
    from windowstolinux.resolver import cache
    cache.set("repology:unknowntool", "")

    result = lookup("unknowntool")
    assert result is None


# ---------------------------------------------------------------------------
# lookup - successful HTTP
# ---------------------------------------------------------------------------


def test_lookup_fetches_when_no_cache(mocker) -> None:
    data = [{"repo": "ubuntu_24_04", "binname": "vlc"}]
    mocker.patch("windowstolinux.resolver.repology.httpx.get", return_value=_make_http_response(data))

    result = lookup("vlc")
    assert result == "vlc"


def test_lookup_normalises_input_to_lowercase(mocker) -> None:
    data = [{"repo": "ubuntu_24_04", "binname": "vlc"}]
    mock_get = mocker.patch(
        "windowstolinux.resolver.repology.httpx.get",
        return_value=_make_http_response(data),
    )

    lookup("VLC")

    call_url = mock_get.call_args[0][0]
    assert call_url.endswith("/vlc")


def test_lookup_stores_result_in_cache(mocker) -> None:
    data = [{"repo": "ubuntu_24_04", "binname": "vlc"}]
    mocker.patch("windowstolinux.resolver.repology.httpx.get", return_value=_make_http_response(data))

    lookup("vlc")

    from windowstolinux.resolver import cache
    assert cache.get("repology:vlc") == "vlc"


def test_lookup_stores_sentinel_when_not_found(mocker) -> None:
    data = [{"repo": "arch", "binname": "some-arch-pkg"}]
    mocker.patch("windowstolinux.resolver.repology.httpx.get", return_value=_make_http_response(data))

    result = lookup("windowsonly")

    assert result is None
    from windowstolinux.resolver import cache
    assert cache.get("repology:windowsonly") == ""


# ---------------------------------------------------------------------------
# lookup - HTML disambiguation (non-JSON response)
# ---------------------------------------------------------------------------


def test_lookup_html_response_returns_none(mocker) -> None:
    mocker.patch(
        "windowstolinux.resolver.repology.httpx.get",
        return_value=_make_http_response(json_data=None),  # .json() raises ValueError
    )

    result = lookup("ambiguous")
    assert result is None


def test_lookup_html_response_caches_sentinel(mocker) -> None:
    mocker.patch(
        "windowstolinux.resolver.repology.httpx.get",
        return_value=_make_http_response(json_data=None),
    )

    lookup("ambiguous")

    from windowstolinux.resolver import cache
    assert cache.get("repology:ambiguous") == ""


# ---------------------------------------------------------------------------
# lookup - network errors
# ---------------------------------------------------------------------------


def test_lookup_network_error_returns_none_when_no_cache(mocker) -> None:
    import httpx as _httpx
    mocker.patch(
        "windowstolinux.resolver.repology.httpx.get",
        side_effect=_httpx.ConnectError("timeout"),
    )

    assert lookup("vlc") is None


def test_lookup_network_error_falls_back_to_stale_cache(mocker, monkeypatch) -> None:
    import httpx as _httpx
    import windowstolinux.resolver.cache as cache_mod

    # Pre-populate a stale entry
    from windowstolinux.resolver import cache
    cache.set("repology:vlc", "vlc")
    monkeypatch.setattr(cache_mod, "_TTL_SECONDS", 0)  # expire everything

    mocker.patch(
        "windowstolinux.resolver.repology.httpx.get",
        side_effect=_httpx.ConnectError("offline"),
    )

    result = lookup("vlc")
    assert result == "vlc"


def test_lookup_network_error_stale_sentinel_returns_none(mocker, monkeypatch) -> None:
    import httpx as _httpx
    import windowstolinux.resolver.cache as cache_mod

    from windowstolinux.resolver import cache
    cache.set("repology:unknown", "")
    monkeypatch.setattr(cache_mod, "_TTL_SECONDS", 0)

    mocker.patch(
        "windowstolinux.resolver.repology.httpx.get",
        side_effect=_httpx.ConnectError("offline"),
    )

    assert lookup("unknown") is None
