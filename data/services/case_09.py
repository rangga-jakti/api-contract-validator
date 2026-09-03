from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Any
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

class WebhookPayload(BaseModel):
    event: str
    payload: Any

def _log_webhook_event(event: str, source_ip: str):
    """Log incoming webhook for audit trail."""
    logger.info(f"Webhook received: event={event} source={source_ip}")

def _process_event(event: str, payload: Any) -> bool:
    """Route event to appropriate handler."""
    handlers = {
        "order.created": lambda p: True,
        "order.cancelled": lambda p: True,
        "payment.received": lambda p: True,
    }
    handler = handlers.get(event)
    return handler(payload) if handler else False

# VIOLATION: spec requires X-Webhook-Secret header (required: true)
# but this endpoint does not validate it at all
@app.post("/webhooks")
async def receive_webhook(request: Request, body: WebhookPayload):
    client_ip = request.client.host
    _log_webhook_event(body.event, client_ip)
    success = _process_event(body.event, body.payload)
    return {"received": True, "processed": success}
