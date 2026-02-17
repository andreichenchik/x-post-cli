"""Tweet text length helpers."""

import re

_SHORT_URL_LENGTH = 23
_URL_RE = re.compile(r"https?://\S+", flags=re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,!?;:'\""


def count_tweet_length(text: str) -> int:
    """Return tweet length using X URL-shortening counting rules."""
    length = 0
    cursor = 0

    for match in _URL_RE.finditer(text):
        start, end = match.span()
        _, suffix = _split_url_and_suffix(match.group(0))
        end -= len(suffix)
        length += len(text[cursor:start])
        length += _SHORT_URL_LENGTH
        cursor = end

    length += len(text[cursor:])
    return length


def _split_url_and_suffix(candidate: str) -> tuple[str, str]:
    """Split URL candidate from trailing punctuation that should not be shortened."""
    suffix_chars: list[str] = []
    url = candidate

    while url:
        last = url[-1]
        if last in _TRAILING_PUNCTUATION:
            suffix_chars.append(last)
            url = url[:-1]
            continue
        if last == ")" and url.count(")") > url.count("("):
            suffix_chars.append(last)
            url = url[:-1]
            continue
        break

    return url, "".join(reversed(suffix_chars))
