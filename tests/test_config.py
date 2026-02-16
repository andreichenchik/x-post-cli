"""Tests for JsonConfigStore and prompt_if_missing."""

import json
import os
import pathlib

import pytest

from x_post.config import JsonConfigStore, prompt_if_missing

from helpers import DictConfigStore


# --- JsonConfigStore ---


class TestJsonConfigStore:
    def test_get_returns_none_when_file_missing(self, tmp_path: pathlib.Path) -> None:
        store = JsonConfigStore(tmp_path / "missing" / "config.json")
        assert store.get("anything") is None

    def test_set_creates_file_and_dirs(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "sub" / "config.json"
        store = JsonConfigStore(path)
        store.set("key", "val")
        assert path.exists()
        assert json.loads(path.read_text()) == {"key": "val"}

    def test_set_preserves_existing_keys(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "config.json"
        store = JsonConfigStore(path)
        store.set("a", "1")
        store.set("b", "2")
        assert json.loads(path.read_text()) == {"a": "1", "b": "2"}

    def test_set_many_writes_multiple_keys(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "config.json"
        store = JsonConfigStore(path)
        store.set_many({"x": "10", "y": "20"})
        assert json.loads(path.read_text()) == {"x": "10", "y": "20"}

    def test_remove_deletes_keys(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "config.json"
        store = JsonConfigStore(path)
        store.set_many({"a": "1", "b": "2", "c": "3"})
        store.remove(["a", "c"])
        assert json.loads(path.read_text()) == {"b": "2"}

    def test_remove_ignores_missing_keys(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "config.json"
        store = JsonConfigStore(path)
        store.set("a", "1")
        store.remove(["nonexistent"])
        assert json.loads(path.read_text()) == {"a": "1"}

    def test_file_permissions(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "config.json"
        store = JsonConfigStore(path)
        store.set("secret", "value")
        mode = os.stat(path).st_mode & 0o777
        assert mode == 0o600


# --- prompt_if_missing ---


class TestPromptIfMissing:
    def test_returns_existing_value_without_prompting(self) -> None:
        config = DictConfigStore({"key": "existing"})
        called = False

        def fake_prompt(_msg: str) -> str:
            nonlocal called
            called = True
            return "new"

        result = prompt_if_missing(config, "key", "Key", prompt_fn=fake_prompt)
        assert result == "existing"
        assert not called

    def test_prompts_and_saves_when_missing(self) -> None:
        config = DictConfigStore()
        result = prompt_if_missing(
            config, "key", "Key", prompt_fn=lambda _: "user-input",
        )
        assert result == "user-input"
        assert config.get("key") == "user-input"

    def test_exits_on_empty_input(self) -> None:
        config = DictConfigStore()
        with pytest.raises(SystemExit):
            prompt_if_missing(config, "key", "Key", prompt_fn=lambda _: "")
