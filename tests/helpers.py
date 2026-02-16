"""Shared test utilities."""


class DictConfigStore:
    """In-memory ConfigStore for tests."""

    def __init__(self, data: dict[str, str] | None = None) -> None:
        self._data: dict[str, str] = dict(data) if data else {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def set_many(self, items: dict[str, str]) -> None:
        self._data.update(items)

    def remove(self, keys: list[str]) -> None:
        for k in keys:
            self._data.pop(k, None)

    @property
    def data(self) -> dict[str, str]:
        return self._data
