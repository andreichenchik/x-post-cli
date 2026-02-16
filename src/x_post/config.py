"""Persistent JSON config store for credentials."""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Callable, Protocol

_DEFAULT_PATH = pathlib.Path.home() / ".config" / "x-post-cli" / "config.json"


class ConfigStore(Protocol):
    """Read/write access to persistent key-value config."""

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def set_many(self, items: dict[str, str]) -> None: ...
    def remove(self, keys: list[str]) -> None: ...


class JsonConfigStore:
    """Config store backed by a JSON file (default ``~/.config/x-post-cli/config.json``).

    Creates the directory and file on first write.  Sets ``0o600`` permissions
    after each write to protect secrets.
    """

    def __init__(self, path: pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = path

    def get(self, key: str) -> str | None:
        data = self._read()
        return data.get(key)

    def set(self, key: str, value: str) -> None:
        data = self._read()
        data[key] = value
        self._write(data)

    def set_many(self, items: dict[str, str]) -> None:
        data = self._read()
        data.update(items)
        self._write(data)

    def remove(self, keys: list[str]) -> None:
        data = self._read()
        for k in keys:
            data.pop(k, None)
        self._write(data)

    def _read(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8",
        )
        os.chmod(self._path, 0o600)


def prompt_if_missing(
    config: ConfigStore,
    key: str,
    display_name: str,
    *,
    prompt_fn: Callable[[str], str] | None = None,
) -> str:
    """Return the value for *key*, prompting the user if it's not stored yet.

    Saves the prompted value into *config* for next time.
    Exits if the user provides an empty value.
    """
    value = config.get(key)
    if value:
        return value
    _prompt = prompt_fn or input
    value = _prompt(f"{display_name}: ")
    if not value or not value.strip():
        print("Value required. Aborting.", file=sys.stderr)
        sys.exit(1)
    value = value.strip()
    config.set(key, value)
    return value
