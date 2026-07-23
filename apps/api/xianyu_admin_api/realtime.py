"""Small in-process event broker for browser realtime updates."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from .settings import settings


REALTIME_REDIS_CHANNEL = "xianyu:realtime-events"
logger = logging.getLogger(__name__)
_publish_client: redis.Redis | None = None


class RealtimeBroker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()
        self._published = 0
        self._resync_required = 0

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = tuple(self._subscribers)
            self._published += 1
        for queue in subscribers:
            if queue.full():
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                queue.put_nowait({"event": "resync_required"})
                self._resync_required += 1
                continue
            queue.put_nowait(event)

    async def health(self) -> dict[str, int]:
        async with self._lock:
            subscribers = tuple(self._subscribers)
            return {
                "subscribers": len(subscribers),
                "queued": sum(queue.qsize() for queue in subscribers),
                "capacity_per_subscriber": 200,
                "published": self._published,
                "resync_required": self._resync_required,
            }


realtime_broker = RealtimeBroker()


async def publish_cross_process(event: dict[str, Any]) -> None:
    global _publish_client
    if _publish_client is None:
        _publish_client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
    try:
        await _publish_client.publish(
            REALTIME_REDIS_CHANNEL,
            json.dumps(event, ensure_ascii=False, separators=(",", ":")),
        )
    except (RedisError, OSError):
        logger.warning("Cross-process realtime publish failed", exc_info=True)


async def relay_cross_process_events() -> None:
    while True:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        try:
            await pubsub.subscribe(REALTIME_REDIS_CHANNEL)
            while True:
                message = await pubsub.get_message(timeout=1.0)
                if message and message.get("type") == "message":
                    try:
                        payload = json.loads(message["data"])
                    except (TypeError, ValueError):
                        continue
                    if isinstance(payload, dict):
                        await realtime_broker.publish(payload)
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            raise
        except (RedisError, OSError):
            logger.warning("Cross-process realtime relay disconnected", exc_info=True)
            await asyncio.sleep(2)
        finally:
            await pubsub.aclose()
            await client.aclose()


async def close_cross_process_publisher() -> None:
    global _publish_client
    if _publish_client is not None:
        await _publish_client.aclose()
        _publish_client = None
