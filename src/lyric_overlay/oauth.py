"""Spotipy's loopback flow with a deadline and cancellation for a windowed app."""
from __future__ import annotations

import secrets
import threading
import time
from urllib.parse import urlparse

from spotipy.oauth2 import RequestHandler, SpotifyOAuth, start_local_http_server


class CallbackHandler(RequestHandler):
    # Bound an accepted connection too, so a half-open request cannot prevent
    # cancellation or monopolize the loopback server.
    timeout = 0.5


class OAuthInteractionError(RuntimeError):
    retryable = False


class DesktopSpotifyOAuth(SpotifyOAuth):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("state", secrets.token_urlsafe(24))
        kwargs.setdefault("requests_timeout", 3)
        super().__init__(*args, **kwargs)
        self._cancelled = threading.Event()

    def prepare(self) -> None:
        self._cancelled.clear()

    def cancel(self) -> None:
        self._cancelled.set()

    def get_auth_response(self, open_browser=None):
        uri = urlparse(self.redirect_uri)
        if uri.scheme != "http" or uri.hostname != "127.0.0.1" or not uri.port:
            raise OAuthInteractionError(
                "Use an HTTP loopback redirect with a port, such as "
                "http://127.0.0.1:8888/callback, in Settings and Spotify's dashboard."
            )
        if self._cancelled.is_set():
            raise OAuthInteractionError("Spotify login canceled. Reload playback to try again.")
        # Fresh state for each browser interaction; never fall back to stdin.
        self.state = secrets.token_urlsafe(24)
        try:
            server = start_local_http_server(uri.port, handler=CallbackHandler)
        except OSError as exc:
            raise OAuthInteractionError(
                "Spotify callback port is unavailable. Close the other login attempt or change the redirect port."
            ) from exc
        try:
            server.timeout = 0.2
            self._open_auth_url()
            deadline = time.monotonic() + 120
            while not self._cancelled.is_set() and time.monotonic() < deadline:
                server.handle_request()
                if server.error is not None:
                    raise OAuthInteractionError("Spotify login was declined. Reload playback to try again.")
                if server.auth_code is not None:
                    if getattr(server, "state", None) != self.state:
                        raise OAuthInteractionError("Spotify login could not be verified. Reload playback to try again.")
                    return server.auth_code
            raise OAuthInteractionError("Spotify login canceled or timed out. Reload playback to try again.")
        finally:
            server.server_close()
