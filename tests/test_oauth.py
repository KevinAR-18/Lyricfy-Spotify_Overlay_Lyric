from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from spotipy.cache_handler import MemoryCacheHandler

from lyric_overlay import oauth


def auth():
    return oauth.DesktopSpotifyOAuth(client_id="test-id", client_secret="test-secret",
                                    redirect_uri="http://127.0.0.1:8888/callback", cache_handler=MemoryCacheHandler())


def test_oauth_callback_and_server_cleanup(monkeypatch):
    value = auth()
    server = SimpleNamespace(auth_code=None, error=None, server_close=Mock())
    def callback():
        server.auth_code = "authorization-code"
        server.state = value.state
    server.handle_request = callback
    monkeypatch.setattr(oauth, "start_local_http_server", lambda *a, **kw: server)
    value._open_auth_url = Mock()
    assert value.get_auth_response() == "authorization-code"
    value._open_auth_url.assert_called_once()
    server.server_close.assert_called_once()


def test_oauth_cancel_releases_callback_port(monkeypatch):
    value = auth()
    server = SimpleNamespace(auth_code=None, error=None, handle_request=value.cancel, server_close=Mock())
    monkeypatch.setattr(oauth, "start_local_http_server", lambda *a, **kw: server)
    value._open_auth_url = Mock()
    with pytest.raises(oauth.OAuthInteractionError, match="canceled"):
        value.get_auth_response()
    server.server_close.assert_called_once()


def test_oauth_occupied_port_does_not_fall_back_to_stdin(monkeypatch):
    value = auth()
    monkeypatch.setattr(oauth, "start_local_http_server", Mock(side_effect=OSError("address in use")))
    value._get_auth_response_interactive = Mock(side_effect=AssertionError("stdin fallback"))
    with pytest.raises(oauth.OAuthInteractionError, match="port is unavailable"):
        value.get_auth_response()


@pytest.mark.parametrize("uri", ["http://localhost:8888/callback", "https://example.org/callback", "http://127.0.0.1/callback"])
def test_oauth_requires_loopback_with_port(uri):
    value = auth()
    value.redirect_uri = uri
    with pytest.raises(oauth.OAuthInteractionError, match="loopback"):
        value.get_auth_response()


def test_oauth_invalid_state_closes_server(monkeypatch):
    value = auth()
    server = SimpleNamespace(auth_code="code", error=None, state="wrong", handle_request=Mock(), server_close=Mock())
    monkeypatch.setattr(oauth, "start_local_http_server", lambda *a, **kw: server)
    value._open_auth_url = Mock()
    with pytest.raises(oauth.OAuthInteractionError, match="verified"):
        value.get_auth_response()
    server.server_close.assert_called_once()
