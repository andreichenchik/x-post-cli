# x-post

CLI utility for publishing tweets to Twitter/X via the official API.

## Prerequisites

1. Create a project and app at https://developer.x.com
2. In **User authentication settings** → Enable OAuth 2.0
3. Type of App: **Native App** (public client, PKCE)
4. Callback URL: `http://localhost:8000/callback`
5. Scopes: `tweet.write`, `tweet.read`, `users.read`, `offline.access`
6. Copy `Client ID` and `Client Secret`

## Setup

```bash
cp .env.example .env
# Fill in CLIENT_ID and CLIENT_SECRET
```

## Usage

```bash
# Inline text
uv run x-post "My first tweet via API!"

# From file
uv run x-post --from-file draft.txt

# Interactive input (Ctrl+D to send)
uv run x-post

# Force re-authorization
uv run x-post --auth
```

On first run, a browser window will open for OAuth authorization. Tokens are saved to `.env` automatically and refreshed when expired.

## Tests

```bash
uv run pytest
```
