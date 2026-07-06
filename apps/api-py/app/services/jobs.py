from __future__ import annotations

from typing import Any, Callable

from celery.exceptions import CeleryError, OperationalError
import redis

from app.core.config import settings


def enqueue_or_run(task: Any, args: tuple, fallback: Callable[[], dict]) -> dict:
    """Submit to Celery when available; keep MVP workflows usable without Redis."""
    try:
        ensure_broker_available()
        result = task.apply_async(args=args)
        return {"execution": "queued", "taskId": result.id}
    except (CeleryError, OperationalError, OSError, ConnectionError, RuntimeError, redis.RedisError) as exc:
        payload = fallback()
        payload["execution"] = "sync"
        payload["queueError"] = str(exc)
        return payload


def ensure_broker_available() -> None:
    if settings.celery_broker_url.startswith("redis://"):
        redis.Redis.from_url(settings.celery_broker_url, socket_connect_timeout=0.3, socket_timeout=0.3).ping()



def revoke_task(task_id: str, *, terminate: bool = False) -> dict:
    """Best-effort Celery revoke for visible task ids; never hides business-state cancellation."""
    try:
        ensure_broker_available()
        from app.worker.celery_app import celery_app

        celery_app.control.revoke(task_id, terminate=terminate, signal="SIGTERM")
        return {"revoked": True, "terminate": terminate}
    except (CeleryError, OperationalError, OSError, ConnectionError, RuntimeError, redis.RedisError) as exc:
        return {"revoked": False, "message": str(exc)}
