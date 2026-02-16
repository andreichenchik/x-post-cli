"""X API client for creating posts."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Protocol

import requests
from requests_oauthlib import OAuth1

_BASE_URL = "https://api.x.com/2"
_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
_SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


@dataclass(frozen=True)
class OAuth1Credentials:
    """OAuth 1.0a credentials required for media uploads."""

    api_key: str
    api_key_secret: str
    access_token: str
    access_token_secret: str


@dataclass(frozen=True)
class TweetResult:
    """Result of publishing a tweet."""

    tweet_id: str
    url: str


class XAPI(Protocol):
    """Interface for X API operations."""

    def get_username(self) -> str:
        """Return the authenticated user's username."""
        ...

    def create_tweet(
        self,
        text: str,
        *,
        reply_to_tweet_id: str | None = None,
        media_ids: list[str] | None = None,
    ) -> TweetResult:
        """Publish a tweet and return the result with ID and URL."""
        ...


class XClient:
    """HTTP client for X REST API v2.

    Usage::

        client = XClient(access_token="...")
        url = client.create_tweet("Hello X!")
    """

    def __init__(
        self,
        access_token: str,
        *,
        oauth1: OAuth1Credentials | None = None,
    ) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {access_token}",
        })
        self._oauth1 = oauth1
        self._username: str | None = None

    def get_username(self) -> str:
        """Return the authenticated user's @username (cached)."""
        if self._username is None:
            resp = self._session.get(f"{_BASE_URL}/users/me")
            resp.raise_for_status()
            self._username = resp.json()["data"]["username"]
        return self._username

    def upload_media(self, path: pathlib.Path) -> str:
        """Upload an image file and return the media_id string.

        Requires OAuth 1.0a credentials (passed via ``oauth1`` at construction).
        Supports jpg, png, gif, webp up to 5 MB.
        Raises ``ValueError`` for unsupported format, oversized files,
        or missing OAuth 1.0a credentials.
        """
        if self._oauth1 is None:
            raise ValueError(
                "OAuth 1.0a credentials are required for media uploads.",
            )
        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED_IMAGE_TYPES:
            raise ValueError(
                f"Unsupported image format '{suffix}'. "
                f"Supported: {', '.join(sorted(_SUPPORTED_IMAGE_TYPES))}",
            )
        size = path.stat().st_size
        if size > _MAX_IMAGE_SIZE:
            raise ValueError(
                f"Image too large ({size / 1024 / 1024:.1f} MB). "
                f"Maximum: {_MAX_IMAGE_SIZE / 1024 / 1024:.0f} MB",
            )
        auth = OAuth1(
            self._oauth1.api_key,
            self._oauth1.api_key_secret,
            self._oauth1.access_token,
            self._oauth1.access_token_secret,
        )
        with open(path, "rb") as f:
            resp = requests.post(_UPLOAD_URL, files={"media": f}, auth=auth)
        if not resp.ok:
            raise requests.HTTPError(
                f"{resp.status_code}: {resp.text}", response=resp,
            )
        return str(resp.json()["media_id"])

    def create_tweet(
        self,
        text: str,
        *,
        reply_to_tweet_id: str | None = None,
        media_ids: list[str] | None = None,
    ) -> TweetResult:
        """Publish a tweet, optionally with media or as a reply."""
        body: dict = {"text": text}
        if reply_to_tweet_id is not None:
            body["reply"] = {"in_reply_to_tweet_id": reply_to_tweet_id}
        if media_ids is not None:
            body["media"] = {"media_ids": media_ids}

        resp = self._session.post(f"{_BASE_URL}/tweets", json=body)
        if not resp.ok:
            raise requests.HTTPError(
                f"{resp.status_code}: {resp.text}", response=resp,
            )
        tweet_id = resp.json()["data"]["id"]
        username = self.get_username()
        return TweetResult(
            tweet_id=tweet_id,
            url=f"https://x.com/{username}/status/{tweet_id}",
        )
