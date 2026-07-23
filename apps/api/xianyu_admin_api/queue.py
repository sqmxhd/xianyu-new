"""Background task queue integration.

Database rows remain the source of truth. Redis is only the delivery channel for
task IDs, so losing Redis messages does not destroy task payloads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import redis.asyncio as redis

from .schemas import BackgroundTaskPayload
from .settings import settings
from .store import AccountStore


@dataclass(slots=True)
class EnqueueResult:
    queued: bool
    backend: str
    message: str


class QueueUnavailableError(RuntimeError):
    """Raised when a durable task cannot be handed to the Redis worker."""


TASK_QUEUE_NAME = "xianyu-admin"


def resolve_broker_url() -> str:
    return settings.redis_url


async def enqueue_background_task(
    store: AccountStore,
    task: BackgroundTaskPayload,
) -> EnqueueResult:
    # Keep the store argument for the stable caller contract. Task payloads remain
    # durable in the database, while Redis is the mandatory delivery channel.
    _ = store
    broker_url = resolve_broker_url()
    if not broker_url:
        raise QueueUnavailableError("redis broker url is not configured")

    client = redis.Redis.from_url(broker_url)
    try:
        await client.lpush(TASK_QUEUE_NAME, json.dumps({"task_id": task.task_id}, ensure_ascii=False))
        return EnqueueResult(True, "redis", "queued")
    finally:
        await client.aclose()
