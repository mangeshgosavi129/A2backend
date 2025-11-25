import json
import logging
from typing import Mapping, Tuple, Optional
import requests
from .config import WhatsAppConfig

# Setup logger
logger = logging.getLogger(__name__)

def _api_url(config: WhatsAppConfig) -> str:
    return f"https://graph.facebook.com/{config.VERSION}/{config.PHONE_NUMBER_ID}/messages"

def _get_text_payload(recipient: str, text: str) -> str:
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def send_whatsapp_text(
    to: str, 
    text: str, 
    config: Optional[WhatsAppConfig] = None
) -> Tuple[Mapping, int]:
    """
    Sends a WhatsApp message.
    
    Arguments:
        to (str): The recipient's phone number.
        text (str): The message body.
        config (WhatsAppConfig, optional): Dependency injection for config.
    """
    # Initialize config if not provided (prevents crash if called without it)
    if config is None:
        cfg = WhatsAppConfig()
    else:
        cfg = config

    recipient = to
    
    # Validation
    if not (cfg.ACCESS_TOKEN and cfg.VERSION and cfg.PHONE_NUMBER_ID and recipient):
        logger.error("Missing WhatsApp configuration or recipient")
        return {"status": "error", "message": "Missing configuration"}, 500

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {cfg.ACCESS_TOKEN}",
    }

    try:
        # Timeout increased to 15s
        resp = requests.post(
            _api_url(cfg), 
            data=_get_text_payload(recipient, text), 
            headers=headers, 
            timeout=15
        )
        resp.raise_for_status()
        return resp.json(), resp.status_code

    except requests.Timeout:
        logger.error("WhatsApp request timed out")
        return {"status": "error", "message": "Request timed out"}, 408

    except requests.RequestException as e:
        logger.error(f"WhatsApp send error: {e}")
        
        # FIX: Check if 'resp' exists before accessing it to prevent UnboundLocalError
        # 'resp' only exists if the server replied (e.g. 400/500 error). 
        # It does NOT exist if the connection failed entirely (DNS/Network error).
        if 'resp' in locals():
             try:
                 return resp.json(), resp.status_code
             except Exception:
                 pass # Fall through to generic error
        return {"status": "error", "message": "Failed to send message"}, 500

def send_task_notification(phone: str, task_dict: dict, config: Optional[WhatsAppConfig] = None) -> Tuple[Mapping, int]:
    """
    Sends a WhatsApp notification when a task is assigned to a user.
    
    Arguments:
        phone (str): The recipient's phone number.
        task_dict (dict): Task details including title, description, priority, deadline.
        config (WhatsAppConfig, optional): WhatsApp configuration.
    """
    # Format the notification message
    message = f"📋 *New Task Assigned*\n\n"
    message += f"*Title:* {task_dict.get('title', 'N/A')}\n"
    
    if task_dict.get('description'):
        message += f"*Description:* {task_dict['description']}\n"
    
    message += f"*Priority:* {task_dict.get('priority', 'medium').upper()}\n"
    
    if task_dict.get('deadline'):
        message += f"*Deadline:* {task_dict['deadline']}\n"
    
    message += f"\nTask ID: #{task_dict.get('id', 'N/A')}"
    
    # Send the notification
    return send_whatsapp_text(phone, message, config)