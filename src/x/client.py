"""X API client for creating posts."""

from dataclasses import dataclass
from typing import Protocol

import requests

_BASE_URL = "https://api.x.com/2"


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
        self, text: str, *, reply_to_tweet_id: str | None = None,
    ) -> TweetResult:
        """Publish a tweet and return the result with ID and URL."""
        ...


class XClient:
    """HTTP client for X REST API v2.

    Usage::

        client = XClient(access_token="...")
        url = client.create_tweet("Hello X!")
    """

    def __init__(self, access_token: str) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {access_token}",
        })
        self._username: str | None = None

    def get_username(self) -> str:
        """Return the authenticated user's @username (cached)."""
        if self._username is None:
            resp = self._session.get(f"{_BASE_URL}/users/me")
            resp.raise_for_status()
            self._username = resp.json()["data"]["username"]
        return self._username

    def create_tweet(
        self, text: str, *, reply_to_tweet_id: str | None = None,
    ) -> TweetResult:
        """Publish a tweet, optionally as a reply. Returns tweet ID and URL."""
        body: dict = {"text": text}
        if reply_to_tweet_id is not None:
            body["reply"] = {"in_reply_to_tweet_id": reply_to_tweet_id}

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
