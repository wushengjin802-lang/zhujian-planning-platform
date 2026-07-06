from __future__ import annotations

import socket

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.model_gateway import gateway_status
from app.services.office_converter import libreoffice_status
from app.services.storage import storage


def platform_status(db: Session) -> dict:
    return {
        "database": database_status(db),
        "redis": redis_status(),
        "minio": minio_status(),
        "libreOffice": libreoffice_status(),
        "modelGateway": gateway_status(),
    }


def database_status(db: Session) -> dict:
    extensions = {}
    for name in ["postgis", "vector"]:
        row = db.execute(
            text("select installed_version, default_version from pg_available_extensions where name = :name"),
            {"name": name},
        ).mappings().first()
        extensions[name] = {
            "available": bool(row),
            "installed": bool(row and row["installed_version"]),
            "installedVersion": row["installed_version"] if row else None,
            "defaultVersion": row["default_version"] if row else None,
        }
    return {"connected": True, "schema": settings.pg_schema, "extensions": extensions}


def redis_status() -> dict:
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)
        return {"available": bool(client.ping()), "url": redact_url(settings.redis_url)}
    except Exception as exc:
        return {"available": False, "url": redact_url(settings.redis_url), "message": str(exc)}


def minio_status() -> dict:
    try:
        available = storage.minio_available()
        return {"available": available, "endpoint": settings.minio_endpoint, "bucket": settings.minio_bucket}
    except (socket.timeout, OSError) as exc:
        return {"available": False, "endpoint": settings.minio_endpoint, "bucket": settings.minio_bucket, "message": str(exc)}


def redact_url(url: str) -> str:
    if "@" not in url:
        return url
    prefix, suffix = url.rsplit("@", 1)
    scheme = prefix.split("://", 1)[0]
    return f"{scheme}://***@{suffix}"

