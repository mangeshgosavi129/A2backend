from typing import Any, Mapping
import json
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from .queue import push_to_queue
from .security import verify_webhook
import logging
# from mangum import Mangum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Webhook")
# handler = Mangum(app)

@app.get("/health")
async def health() -> Mapping[str, Any]:
    return {"status": "ok"}

@app.get("/webhook")
async def webhook_verify(request: Request) -> Response:
    params = dict(request.query_params)
    logger.info(f"Params from webhook_verify: {params}")
    content, status = verify_webhook(params)
    if isinstance(content, str):
        # Meta expects the plain challenge string
        logger.info(f"Content from webhook_verify: {content}")
        return PlainTextResponse(content, status_code=status)
    return JSONResponse(content, status_code=status)

@app.post("/webhook")
async def webhook_receive(request: Request) -> JSONResponse:
    print("=" * 50)
    print("[webhook_receive] Received POST /webhook request")
    
    raw_body = await request.body()
    print(f"[webhook_receive] Raw body size: {len(raw_body)} bytes")
    
    try:
        body = await request.json()
        print(f"[webhook_receive] Parsed JSON body: {json.dumps(body, indent=2)[:500]}...")  # First 500 chars
    except Exception as e:
        print(f"[webhook_receive] Failed to parse JSON: {e}")
        body = {}
    
    headers = {k: v for k, v in request.headers.items()}
    print(f"[webhook_receive] Headers: {headers}")
    
    print("[webhook_receive] Calling push_to_queue...")
    content, status = push_to_queue(body, headers, raw_body)
    
    print(f"[webhook_receive] Response: status={status}, content={content}")
    print("=" * 50)
    return JSONResponse(content, status_code=status)