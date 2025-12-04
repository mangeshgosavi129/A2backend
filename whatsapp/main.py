from typing import Any, Mapping
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from .webhook import handle_webhook
from .security import verify_webhook

# =========================================================
# PROMETHEUS
# =========================================================
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["endpoint"]
)

EXCEPTION_COUNT = Counter(
    "http_exceptions_total",
    "Total exceptions",
    ["endpoint"]
)

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

# =========================================================
# PROMETHEUS ENDPOINTS
# =========================================================

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(data, media_type=CONTENT_TYPE_LATEST)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()

    try:
        response = await call_next(request)
    except Exception:
        EXCEPTION_COUNT.labels(endpoint=request.url.path).inc()
        raise

    process_time = time.time() - start_time

    REQUEST_LATENCY.labels(endpoint=request.url.path).observe(process_time)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        http_status=response.status_code
    ).inc()

    return response
