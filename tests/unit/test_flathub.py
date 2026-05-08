"""Unit tests for windowstolinux.resolver.flathub."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from windowstolinux.resolver.flathub import _extract_app_id, search


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDOWSTOLINUX_CACHE_PATH", str(tmp_path / "cache.db"))


def _make_http_response(json_data=None, raise_for: Exception | None = None) -> MagicMock:
    resp = MagicMock()
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
# _extract_app_id
# ---------------------------------------------------------------------------


def test_extract_app_id_returns_first_id() -> None:
    data = {"apps": [{"id": "org.gimp.GIMP", "name": "GIMP"}, {"id": "org.other.App"}]}
    assert _extract_app_id(data) == "org.gimp.GIMP"


def test_extract_app_id_empty_apps_list() -> None:
    assert _extract_app_id({"apps": []}) is None


def test_extract_app_id_missing_apps_key() -> None:
    assert _extract_app_id({}) is None


def test_extract_app_id_entry_without_id() -> None:
    data = {"apps": [{"name": "GIMP"}]}
    assert _extract_app_id(data) is None


def test_extract_app_id_apps_is_not_a_list() -> None:
    assert _extract_app_id({"apps": "broken"}) is None


# ---------------------------------------------------------------------------
# search - cache hit
# ---------------------------------------------------------------------------


def test_search_returns_cached_value_without_http(mocker) -> None:
    mock_http = mocker.patch("windowstolinux.resolver.flathub.httpx.get")

    from windowstolinux.resolver import cache
    cache.set("flathub:gimp", "org.gimp.GIMP")

    result = search("GIMP")

    assert result == "org.gimp.GIMP"
    mock_http.assert_not_called()


def test_search_cached_sentinel_returns_none(mocker) -> None:
    mocker.patch("windowstolinux.resolver.flathub.httpx.get")
    from windowstolinux.resolver import cache
    cache.set("flathub:unknownapp", "")

    assert search("UnknownApp") is None


# ---------------------------------------------------------------------------
# search - successful HTTP
# ---------------------------------------------------------------------------


def test_search_fetches_when_no_cache(mocker) -> None:
    data = {"apps": [{"id": "org.gimp.GIMP"}], "totalHits": 1}
    mocker.patch("windowstolinux.resolver.flathub.httpx.get", return_value=_make_http_response(data))

    result = search("GIMP")
    assert result == "org.gimp.GIMP"


def test_search_normalises_query_to_lowercase(mocker) -> None:
    data = {"apps": [{"id": "org.gimp.GIMP"}]}
    mock_get = mocker.patch(
        "windowstolinux.resolver.flathub.httpx.get",
        return_value=_make_http_response(data),
    )

    search("GIMP")

    call_url = mock_get.call_args[0][0]
    assert call_url.endswith("/gimp")


def test_search_stores_result_in_cache(mocker) -> None:
    data = {"apps": [{"id": "org.gimp.GIMP"}]}
    mocker.patch("windowstolinux.resolver.flathub.httpx.get", return_value=_make_http_response(data))

    search("gimp")

    from windowstolinux.resolver import cache
    assert cache.get("flathub:gimp") == "org.gimp.GIMP"


def test_search_stores_sentinel_when_no_results(mocker) -> None:
    data = {"apps": [], "totalHits": 0}
    mocker.patch("windowstolinux.resolver.flathub.httpx.get", return_value=_make_http_response(data))

    result = search("nonexistentapp")

    assert result is None
    from windowstolinux.resolver import cache
    assert cache.get("flathub:nonexistentapp") == ""


# ---------------------------------------------------------------------------
# search - non-JSON response
# ---------------------------------------------------------------------------


def test_search_non_json_response_returns_none(mocker) -> None:
    mocker.patch(
        "windowstolinux.resolver.flathub.httpx.get",
        return_value=_make_http_response(json_data=None),
    )
    assert search("something") is None


def test_search_non_json_caches_sentinel(mocker) -> None:
    mocker.patch(
        "windowstolinux.resolver.flathub.httpx.get",
        return_value=_make_http_response(json_data=None),
    )
    search("something")
    from windowstolinux.resolver import cache
    assert cache.get("flathub:something") == ""


# ---------------------------------------------------------------------------
# search - network errors
# ---------------------------------------------------------------------------


def test_search_network_error_returns_none_when_no_cache(mocker) -> None:
    import httpx as _httpx
    mocker.patch(
        "windowstolinux.resolver.flathub.httpx.get",
        side_effect=_httpx.ConnectError("offline"),
    )
    assert search("gimp") is None


def test_search_network_error_falls_back_to_stale_cache(mocker, monkeypatch) -> None:
    import httpx as _httpx
    import windowstolinux.resolver.cache as cache_mod

    from windowstolinux.resolver import cache
    cache.set("flathub:gimp", "org.gimp.GIMP")
    monkeypatch.setattr(cache_mod, "_TTL_SECONDS", 0)

    mocker.patch(
        "windowstolinux.resolver.flathub.httpx.get",
        side_effect=_httpx.ConnectError("offline"),
    )

    assert search("gimp") == "org.gimp.GIMP"


def test_search_network_error_stale_sentinel_returns_none(mocker, monkeypatch) -> None:
    import httpx as _httpx
    import windowstolinux.resolver.cache as cache_mod

    from windowstolinux.resolver import cache
    cache.set("flathub:nothing", "")
    monkeypatch.setattr(cache_mod, "_TTL_SECONDS", 0)

    mocker.patch(
        "windowstolinux.resolver.flathub.httpx.get",
        side_effect=_httpx.ConnectError("offline"),
    )

    assert search("nothing") is None
