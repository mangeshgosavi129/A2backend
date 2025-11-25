import hmac
import hashlib
from typing import Mapping, Optional, Tuple
from .config import WhatsAppConfig

def verify_webhook(params: Mapping[str, str]) -> Tuple[str | Mapping, int]:
    cfg = WhatsAppConfig()
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    print("Verification began")
    if mode and token and mode == "subscribe" and token == cfg.VERIFY_TOKEN and challenge:
        return str(challenge), 200
    if not (mode and token):
        return {"status": "error", "message": "Missing parameters"}, 400
    return {"status": "error", "message": "Verification failed"}, 403


def validate_signature(raw_body: bytes, headers: Mapping[str, str], app_secret: Optional[str]) -> bool:
    signature = headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256=") or not app_secret:
        return True
    provided = signature[7:]
    expected = hmac.new(bytes(app_secret, "latin-1"), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)

