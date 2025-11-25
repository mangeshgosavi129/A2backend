from typing import Any, Mapping
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from .webhook import handle_webhook
from .security import verify_webhook

app = FastAPI(title="WhatsApp Webhook")

@app.get("/health")
async def health() -> Mapping[str, Any]:
    return {"status": "ok"}

@app.get("/webhook")
async def webhook_verify(request: Request) -> Response:
    params = dict(request.query_params)
    print(params)
    content, status = verify_webhook(params)
    if isinstance(content, str):
        # Meta expects the plain challenge string
        print(content)
        return PlainTextResponse(content, status_code=status)
    return JSONResponse(content, status_code=status)

@app.post("/webhook")
async def webhook_receive(request: Request) -> JSONResponse:
    raw_body = await request.body()
    print(raw_body)
    try:
        body = await request.json()
    except Exception:
        body = {}
    headers = {k: v for k, v in request.headers.items()}
    content, status = handle_webhook(body, headers, raw_body)
    print(content)
    return JSONResponse(content, status_code=status)
