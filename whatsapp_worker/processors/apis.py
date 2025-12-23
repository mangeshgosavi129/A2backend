"""
Internal API client for whatsapp_worker.
All database operations go through HTTP calls to server/routes/internals.py
"""
import logging
import requests
from typing import Optional, List
from ..config import config

logger = logging.getLogger(__name__)

def _api_url(path: str) -> str:
    return f"http://localhost:8000/internals{path}"

def get_user_details(
    phone: Optional[str] = None,
    user_id: Optional[int] = None,
    include_role: bool = False
) -> Optional[dict]:
    """
    Fetch user details by phone or user_id.
    Optionally include role in response.
    """
    try:
        params = {}
        if phone:
            params["phone"] = phone
        if user_id:
            params["user_id"] = user_id
        if include_role:
            params["include_role"] = True
        
        resp = requests.get(_api_url("/user"), params=params, timeout=5)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to get user details: {e}")
        return None

def check_idempotency(whatsapp_id: str) -> bool:
    """Check if message was already processed."""
    try:
        resp = requests.get(_api_url(f"/idempotency/{whatsapp_id}"), timeout=5)
        resp.raise_for_status()
        return resp.json().get("exists", False)
    except requests.RequestException as e:
        logger.error(f"Idempotency check failed: {e}")
        return False

def store_message(
    user_id: Optional[int],
    text_body: str,
    whatsapp_id: str,
    direction: str = "in"
) -> bool:
    """
    Store a message via internal API.
    direction: 'in' for incoming, 'out' for outgoing
    """
    try:
        resp = requests.post(_api_url("/message"), json={
            "user_id": user_id,
            "direction": direction,
            "channel": "whatsapp",
            "message_text": text_body,
            "payload": {"whatsapp_id": whatsapp_id}
        }, timeout=5)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to store message: {e}")
        return False

def get_chat_history(user_id: int, limit: int = 15) -> List[dict]:
    """Get chat history for LLM context."""
    try:
        resp = requests.get(_api_url(f"/history/{user_id}"), params={"limit": limit}, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to get chat history: {e}")
        return []
