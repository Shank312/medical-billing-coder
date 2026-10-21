"""Storage abstraction for uploaded documents.

The development implementation writes to a non-public local directory and is
explicitly NOT production-durable; production should swap in object storage behind
this interface. Stored keys are internally generated and strictly validated so
user input can never reach filesystem paths.
"""
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class StorageError(Exception):
    """Raised for storage failures (never expose paths to callers)."""


_SAFE_KEY_RE = re.compile(r"[a-f0-9]{64}")


def generate_storage_key(_extension: str = "") -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


class Storage(ABC):
    @abstractmethod
    def open_write(self, key: str) -> BinaryIO:
        """Return a writable binary stream for ``key``."""

    @abstractmethod
    def open(self, key: str) -> BinaryIO:
        """Return a readable binary stream for ``key``."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete ``key`` (idempotent)."""


class LocalFileStorage(Storage):
    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY_RE.fullmatch(key):
            raise StorageError("Invalid storage key")
        return self.base_dir / key

    def open_write(self, key: str) -> BinaryIO:
        return open(self._path(key), "wb")

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.exists():
            raise StorageError("Object not found")
        return open(path, "rb")

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()
