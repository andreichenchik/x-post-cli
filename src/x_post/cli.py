"""CLI entry-point for x-post."""

import argparse
import pathlib
import sys

from x_post.auth import authenticate, is_token_valid, refresh_access_token
from x_post.client import OAuth1Credentials, XClient
from x_post.config import ConfigStore, JsonConfigStore, prompt_if_missing
from x_post.text import count_tweet_length

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
        "--reply-to",
        type=str,
        metavar="TWEET_ID",
        help="Tweet ID to reply to (for threading)",
    )
    parser.add_argument(
        "--image",
        type=pathlib.Path,
        metavar="PATH",
        help="Attach an image (jpg/png/gif/webp, max 5 MB)",
    )
    parser.add_argument(
        "--reset-auth",
        action="store_true",
        help="Clear saved OAuth 2.0 tokens and re-authorize",
    )
    parser.add_argument(
        "--reset-keys",
        action="store_true",
        help="Clear all saved credentials and re-prompt from scratch",
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
    config: ConfigStore,
    client_id: str,
    client_secret: str,
    *,
    force: bool,
) -> str:
    """Return a valid access token, running OAuth if needed."""
    access_token = config.get("access_token")
    refresh_token = config.get("refresh_token")

    if not force and access_token and is_token_valid(access_token):
        return access_token

    if not force and refresh_token:
        try:
            new_access, new_refresh = refresh_access_token(
                client_id, client_secret, refresh_token,
            )
            config.set_many({
                "access_token": new_access,
                "refresh_token": new_refresh,
            })
            return new_access
        except Exception:
            pass  # fall through to full auth

    new_access, new_refresh = authenticate(client_id, client_secret)
    config.set_many({"access_token": new_access, "refresh_token": new_refresh})
    return new_access


def _ensure_oauth1(config: ConfigStore) -> OAuth1Credentials:
    """Return OAuth 1.0a credentials, prompting for any missing keys."""
    if not config.get("api_key"):
        print(
            "\n"
            "Image upload requires OAuth 1.0a credentials\n"
            "=============================================\n"
            "In your app at https://developer.x.com:\n"
            "\n"
            "1. Go to Keys and Tokens tab\n"
            "2. Under Consumer Keys, copy API Key and API Key Secret\n"
            "3. Under Authentication Tokens, generate Access Token and Secret\n"
            "   (make sure the token has Read and Write permissions)\n",
        )

    return OAuth1Credentials(
        api_key=prompt_if_missing(config, "api_key", "API Key"),
        api_key_secret=prompt_if_missing(config, "api_key_secret", "API Key Secret"),
        access_token=prompt_if_missing(config, "oauth1_access_token", "OAuth 1.0a Access Token"),
        access_token_secret=prompt_if_missing(
            config, "oauth1_access_token_secret", "OAuth 1.0a Access Token Secret",
        ),
    )


def main(argv: list[str] | None = None, *, _config: ConfigStore | None = None) -> None:
    args = _parse_args(argv)
    config = _config or JsonConfigStore()

    if args.reset_keys:
        config.remove([
            "client_id", "client_secret",
            "access_token", "refresh_token",
            "api_key", "api_key_secret",
            "oauth1_access_token", "oauth1_access_token_secret",
        ])
    elif args.reset_auth:
        config.remove(["access_token", "refresh_token"])

    if not config.get("client_id"):
        print(
            "\n"
            "First-time setup\n"
            "================\n"
            "You need OAuth 2.0 credentials from the X Developer Portal.\n"
            "\n"
            "1. Go to https://developer.x.com and create a project & app\n"
            "2. In User authentication settings, enable OAuth 2.0\n"
            "3. Set type to Native App, callback URL: http://localhost:8000/callback\n"
            "4. Copy the Client ID and Client Secret below\n",
        )

    client_id = prompt_if_missing(config, "client_id", "Client ID")
    client_secret = prompt_if_missing(config, "client_secret", "Client Secret")

    text = _read_post_text(args)
    if not text:
        print("Empty tweet text, aborting.", file=sys.stderr)
        sys.exit(1)
    tweet_length = count_tweet_length(text)
    if tweet_length > _MAX_LENGTH:
        print(
            f"Tweet too long: {tweet_length}/{_MAX_LENGTH} characters.",
            file=sys.stderr,
        )
        sys.exit(1)

    access_token = _ensure_token(
        config, client_id, client_secret,
        force=args.reset_auth,
    )

    oauth1: OAuth1Credentials | None = None
    if args.image:
        oauth1 = _ensure_oauth1(config)

    client = XClient(access_token, oauth1=oauth1)

    media_ids: list[str] | None = None
    if args.image:
        if not args.image.exists():
            print(f"Image not found: {args.image}", file=sys.stderr)
            sys.exit(1)
        try:
            media_id = client.upload_media(args.image)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        media_ids = [media_id]

    result = client.create_tweet(
        text, reply_to_tweet_id=args.reply_to, media_ids=media_ids,
    )
    print(f"Tweet published!\n{result.url}")
    print(f"\nTo continue this thread:\n"
          f"x-post-cli --reply-to {result.tweet_id} \"Next tweet text\"")
