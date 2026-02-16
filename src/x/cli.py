"""CLI entry-point for x-post."""

import argparse
import pathlib
import sys

import dotenv

from x.auth import authenticate, is_token_valid, refresh_access_token
from x.client import XClient

_ENV_PATH = pathlib.Path.cwd() / ".env"
_MAX_LENGTH = 280


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a tweet on Twitter/X.",
    )
    parser.add_argument("text", nargs="?", help="Tweet text (inline)")
    parser.add_argument(
        "--from-file", type=pathlib.Path, help="Read tweet text from a file",
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Force re-authorization even if a token exists",
    )
    return parser.parse_args(argv)


def _read_post_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.from_file:
        return args.from_file.read_text(encoding="utf-8").strip()
    print("Enter tweet text (Ctrl+D to send):")
    return sys.stdin.read().strip()


def _ensure_token(
    client_id: str,
    client_secret: str,
    access_token: str | None,
    refresh_token: str | None,
    *,
    force: bool,
) -> tuple[str, str | None]:
    """Return a valid (access_token, refresh_token), running OAuth if needed."""
    if not force and access_token and is_token_valid(access_token):
        return access_token, refresh_token

    if not force and refresh_token:
        try:
            new_access, new_refresh = refresh_access_token(
                client_id, client_secret, refresh_token,
            )
            dotenv.set_key(str(_ENV_PATH), "ACCESS_TOKEN", new_access)
            dotenv.set_key(str(_ENV_PATH), "REFRESH_TOKEN", new_refresh)
            return new_access, new_refresh
        except Exception:
            pass  # fall through to full auth

    new_access, new_refresh = authenticate(client_id, client_secret)
    dotenv.set_key(str(_ENV_PATH), "ACCESS_TOKEN", new_access)
    dotenv.set_key(str(_ENV_PATH), "REFRESH_TOKEN", new_refresh)
    return new_access, new_refresh


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    dotenv.load_dotenv(_ENV_PATH)

    import os

    client_id = os.getenv("CLIENT_ID", "")
    client_secret = os.getenv("CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print(
            "CLIENT_ID and CLIENT_SECRET must be set in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    text = _read_post_text(args)
    if not text:
        print("Empty tweet text, aborting.", file=sys.stderr)
        sys.exit(1)
    if len(text) > _MAX_LENGTH:
        print(
            f"Tweet too long: {len(text)}/{_MAX_LENGTH} characters.",
            file=sys.stderr,
        )
        sys.exit(1)

    access_token, _ = _ensure_token(
        client_id,
        client_secret,
        os.getenv("ACCESS_TOKEN"),
        os.getenv("REFRESH_TOKEN"),
        force=args.auth,
    )

    client = XClient(access_token)
    tweet_url = client.create_tweet(text)
    print(f"Tweet published!\n{tweet_url}")
