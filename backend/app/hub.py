"""Tiny in-process pub/sub for the SSE stream.

Each connected `EventSource` gets its own asyncio queue; a mutation publishes an
event to every queue. No external broker — fine for a single-process local demo
(and the dockerized deploy, as long as it stays one worker). If this ever scales
to multiple workers, swap this for Redis pub/sub behind the same interface.
"""
from __future__ import annotations

import asyncio
from typing import Any


class Hub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    def publish(self, event: dict[str, Any]) -> None:
        """Fan an event out to all current subscribers (non-blocking)."""
        for q in list(self._subscribers):
            q.put_nowait(event)
