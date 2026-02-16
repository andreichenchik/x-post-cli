"""OAuth 2.0 PKCE authentication flow for X."""

import base64
import hashlib
import http.server
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import requests

_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
_TOKEN_URL = "https://api.x.com/2/oauth2/token"
_USERINFO_URL = "https://api.x.com/2/users/me"
_REDIRECT_URI = "http://localhost:8000/callback"
_SCOPES = "tweet.write tweet.read users.read offline.access"


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def is_token_valid(token: str) -> bool:
    """Check whether *token* is still accepted by X API."""
    resp = requests.get(
        _USERINFO_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return resp.status_code == 200


def refresh_access_token(
    client_id: str, client_secret: str, refresh_token: str,
) -> tuple[str, str]:
    """Exchange a refresh token for new access + refresh tokens."""
    resp = requests.post(
        _TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["refresh_token"]


def authenticate(client_id: str, client_secret: str) -> tuple[str, str]:
    """Run the full OAuth 2.0 PKCE browser flow.

    Opens the default browser for user consent, captures the redirect
    on a local server, and exchanges the code for tokens.

    Returns (access_token, refresh_token).
    """
    code_verifier, code_challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)

    auth_code: str | None = None
    error: str | None = None
    server_ready = threading.Event()

    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            nonlocal auth_code, error
            params = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query,
            )

            received_state = params.get("state", [None])[0]
            if received_state != state:
                error = "state_mismatch"
                self._respond("Authorization failed: state mismatch.")
            elif "code" in params:
                auth_code = params["code"][0]
                self._respond("Authorization successful! You can close this tab.")
            else:
                error = params.get("error", ["unknown"])[0]
                self._respond(f"Authorization failed: {error}")

            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def _respond(self, message: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h2>{message}</h2></body></html>".encode(),
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = http.server.HTTPServer(("localhost", 8000), _CallbackHandler)

    def _serve() -> None:
        server_ready.set()
        server.serve_forever()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    server_ready.wait()

    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": _REDIRECT_URI,
        "scope": _SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    authorization_url = f"{_AUTH_URL}?{params}"
    print(f"Opening browser for authorization...\n{authorization_url}")
    webbrowser.open(authorization_url)

    thread.join()

    if error or auth_code is None:
        print(f"Authorization failed: {error}", file=sys.stderr)
        sys.exit(1)

    token_resp = requests.post(
        _TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": _REDIRECT_URI,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )
    token_resp.raise_for_status()
    data = token_resp.json()
    return data["access_token"], data["refresh_token"]
