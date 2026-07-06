from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from fastapi import UploadFile
from minio import Minio
from minio.error import S3Error
import urllib3

from app.core.config import settings


class ObjectStorage:
    def __init__(self) -> None:
        self.documents_dir = settings.storage_root / "documents"
        self.artifacts_dir = settings.storage_root / "artifacts"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            http_client=urllib3.PoolManager(timeout=urllib3.Timeout(connect=0.5, read=0.5), retries=False),
        )

    def minio_available(self) -> bool:
        if settings.storage_mode == "local":
            return False
        try:
            if not self._client.bucket_exists(settings.minio_bucket):
                self._client.make_bucket(settings.minio_bucket)
            return True
        except Exception:
            return False

    def put_file(self, source: Path, key: str, content_type: str = "application/octet-stream") -> str:
        if self.minio_available():
            self._client.fput_object(settings.minio_bucket, key, str(source), content_type=content_type)
            return f"s3://{settings.minio_bucket}/{key}"

        target = settings.storage_root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return str(target)

    def put_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> tuple[str, int]:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            return self.put_file(tmp_path, key, content_type), len(data)
        finally:
            tmp_path.unlink(missing_ok=True)

    def download_to_temp(self, storage_path: str) -> Path:
        if storage_path.startswith("s3://"):
            _, rest = storage_path.split("s3://", 1)
            bucket, key = rest.split("/", 1)
            target = Path(tempfile.gettempdir()) / f"zhujian-{Path(key).name}"
            try:
                self._client.fget_object(bucket, key, str(target))
                return target
            except S3Error as exc:
                raise FileNotFoundError(storage_path) from exc
        path = Path(storage_path)
        if not path.exists():
            raise FileNotFoundError(storage_path)
        return path


storage = ObjectStorage()


async def persist_upload(file: UploadFile, key: str) -> tuple[str, int, str]:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        size = 0
        checksum = hashlib.sha256()
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            checksum.update(chunk)
            tmp.write(chunk)
        tmp_path = Path(tmp.name)
    try:
        storage_path = storage.put_file(tmp_path, key, file.content_type or "application/octet-stream")
        return storage_path, size, checksum.hexdigest()
    finally:
        tmp_path.unlink(missing_ok=True)
