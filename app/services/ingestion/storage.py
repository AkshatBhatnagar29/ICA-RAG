import asyncio
from pathlib import Path

from app.core.exceptions import StorageError


class ObjectStorage:
    async def upload(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    async def download(self, key: str) -> bytes:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError

    async def download_to_path(self, key: str, path: Path) -> None:
        data = await self.download(key)
        await asyncio.to_thread(path.write_bytes, data)


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise StorageError("Invalid storage key")
        return candidate

    async def upload(self, key: str, data: bytes) -> None:
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        try:
            await asyncio.to_thread(write)
        except OSError as exc:
            raise StorageError("Unable to store uploaded file") from exc

    async def download(self, key: str) -> bytes:
        try:
            return await asyncio.to_thread(self._path(key).read_bytes)
        except OSError as exc:
            raise StorageError("Unable to read stored file") from exc

    async def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError as exc:
            raise StorageError("Unable to remove stored file") from exc

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).is_file)
