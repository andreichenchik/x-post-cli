# x-post-cli

CLI utility for publishing tweets to Twitter/X via the official API.

## Install

```bash
# Run directly (no install needed)
uvx x-post-cli@latest "Hello world!"

# Or install globally
uv tool install x-post-cli
```

## Prerequisites

1. Create a project and app at https://developer.x.com
2. In **User authentication settings** → Enable OAuth 2.0
3. Type of App: **Native App** (public client, PKCE)
4. Callback URL: `http://localhost:8000/callback`
5. Copy `Client ID` and `Client Secret`

## Usage

```bash
# First run — you'll be prompted for Client ID and Client Secret
x-post-cli "My first tweet via API!"

# From file
x-post-cli --from-file draft.txt

# Interactive input (Ctrl+D to send)
x-post-cli

# With an image (prompts for OAuth 1.0a keys on first use)
x-post-cli --image photo.jpg "Check this out!"

# Reply to a tweet (threading)
x-post-cli --reply-to 123456789 "Replying!"

# Re-authorize (clears OAuth 2.0 tokens)
x-post-cli --reset-auth "Hello again"

# Clear all credentials and start fresh
x-post-cli --reset-keys "Starting over"
```

Credentials are requested interactively on first run and saved to `~/.config/x-post-cli/config.json`. On subsequent runs no prompts are needed. The config file can also be edited manually.

## Tests

```bash
uv run pytest
```
