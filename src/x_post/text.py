"""Tweet text length helpers."""

import re

_SHORT_URL_LENGTH = 23
_URL_RE = re.compile(r"https?://\S+", flags=re.IGNORECASE)


def count_tweet_length(text: str) -> int:
    """Return tweet length using X URL-shortening counting rules."""
    length = 0
    cursor = 0

    for match in _URL_RE.finditer(text):
        start, end = match.span()
        length += len(text[cursor:start])
        length += _SHORT_URL_LENGTH
        cursor = end

    length += len(text[cursor:])
    return length
