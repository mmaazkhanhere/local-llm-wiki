from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from llm_wiki_backend.observability.events import EVENT_HUB
from llm_wiki_backend.observability.logging import get_logger

router = APIRouter(tags=["Events"])
logger = get_logger("api.ws")


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = await EVENT_HUB.subscribe()
    logger.info("WebSocket client connected")
    try:
        while True:
            event = await queue.get()
            await websocket.send_json({"type": event.event_type, "payload": event.payload})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        await EVENT_HUB.unsubscribe(queue)
