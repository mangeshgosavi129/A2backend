import logging
import json
import requests
import os
from datetime import datetime
import pytz
from typing import Mapping, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .security import validate_signature
from .config import WhatsAppConfig
from .client import send_whatsapp_text
from .database import SessionLocal, User, Message, MessageDirection, MessageChannel
# Assuming this import exists in your project
from llm.main import chat_with_mcp

logger = logging.getLogger(__name__)

def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    # WhatsApp phone numbers often come with country code, e.g., "15551234567"
    # Our DB might store it as "15551234567" or "+15551234567"
    # For MVP, we assume exact match or simple stripping of '+'
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        # Try adding/removing '+'
        if phone.startswith("+"):
            user = db.query(User).filter(User.phone == phone[1:]).first()
        else:
            user = db.query(User).filter(User.phone == f"+{phone}").first()
    return user

def get_chat_history(db: Session, user_id: int, limit: int = 15) -> List[dict]:
    messages = db.query(Message).filter(
        Message.user_id == user_id,
        Message.channel == MessageChannel.whatsapp
    ).order_by(desc(Message.created_at)).limit(limit).all()
    
    # Reverse to chronological order
    messages.reverse()
    
    history = []
    for msg in messages:
        role = "user" if msg.direction == MessageDirection.in_dir else "assistant"
        history.append({"role": role, "content": msg.message_text})
    return history

def get_last_state(db: Session, user_id: int) -> dict:
    last_msg = db.query(Message).filter(
        Message.user_id == user_id
    ).order_by(desc(Message.created_at)).first()
    
    if last_msg and last_msg.user_state:
        return last_msg.user_state
    return {"state": "idle"}

def download_whatsapp_media(media_id: str, access_token: str) -> Optional[bytes]:
    try:
        # 1. Get Media URL
        url = f"https://graph.facebook.com/v22.0/{media_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        media_url = resp.json().get("url")
        
        if not media_url:
            logger.error("No media URL found")
            return None
            
        # 2. Download Binary
        media_resp = requests.get(media_url, headers=headers)
        media_resp.raise_for_status()
        return media_resp.content
    except Exception as e:
        logger.error(f"Failed to download media: {e}")
        return None

def transcribe_audio(audio_binary: bytes) -> str:
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        logger.error("SARVAM_API_KEY not set")
        return "Error: Transcription service not configured."
        
    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": api_key}
    
    # Sarvam expects a file upload. We can send the binary as a file.
    # The model 'saarika:v2.5' is default or specified.
    files = {
        'file': ('audio.ogg', audio_binary, 'audio/ogg') # WhatsApp usually sends OGG
    }
    data = {
        'model': 'saarika:v2.5'
    }
    
    try:
        resp = requests.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()
        result = resp.json()
        return result.get("transcript", "")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return "Error: Could not transcribe audio."

def _generate_response(user_id: int, text: str, db: Session) -> str:
    try:
        # 0. Get User Info
        user = db.query(User).filter(User.id == user_id).first()
        user_name = user.name if user else "Unknown"
        user_dept = user.department if user and user.department else "N/A"
        
        # 1. Fetch History
        history = get_chat_history(db, user_id)
        
        # 2. Fetch State
        state = get_last_state(db, user_id)
        ist_timezone = pytz.timezone('Asia/Kolkata')

        # Get the current datetime in IST
        current_ist_datetime = datetime.now(ist_timezone)
        # 3. Construct System Instruction based on State
        system_instruction = f"""
        You are a WhatsApp task assistant. You must use backend tools for all task changes (list_users, list_tasks, create_task, update_task, assign_task). Never invent IDs/data. Confirm success only after a successful tool response. Default actor is the current user (id {user_id}) unless user clearly specifies someone else.

GOAL:
Ensure the final state in the system matches what the user intends, even if they speak vaguely or fix details later.

=== TASK CREATION FLOW ===
Always follow: DRAFT → CONFIRM → COMMIT

1) DRAFT (no tool calls yet)
• Infer as much as you reasonably can from the user:
  - what(title), who(assignee: default user), when(due or “no deadline”), priority, notes/files
• If any CORE missing/unclear:
  → Ask exactly ONE short clarification question at a time
• When draft is reasonable:
  → Show short summary:
     "Draft:
      Title: ...
      Assignee: ...
      Due: ...
      Files: ...
      Reply 'yes' to create or state changes."

2) CONFIRM
User clearly agrees (“yes”, “create”, “done”)
→ Move to commit

3) COMMIT
• Call create_task once (and assign_task if assignee not default)
• Then confirm using actual data from tool response:
  "Created Task id: title, Due date, Assignee name"

If user abandons the draft and changes topic:
Ask once if they want to keep or discard. If ignored → discard.

=== UPDATING EXISTING TASKS ===
When user refers vaguely (e.g. “the SEO task”):
1) Use list_tasks with simple filters to find matches
2) If multiple:
   Show short numbered list with IDs and key info:
   “[1] ID 143: 'SEO page' Due 30 Nov Assignee Ramesh
    [2] ID 152: 'SEO audit' Due 2 Dec Assignee Priya
    Which ID?”
3) If exactly one match:
   Assume it but say so
4) Ask what to update (status, due, assignee, title, etc.)
5) Call update_task/assign_task only after user specifies change
6) Confirm with the real tool outputs

=== STYLE RULES ===
• Keep replies short and direct
• Don't over-ask if intent is obvious
• Don't call tools without required info
• Don't repeat confirmations unnecessarily
• If uncertain → ask; if clear → act

            CURRENT USER CONTEXT:
            - Name: {user_name}
            - User ID: {user_id}
            - Department: {user_dept}
            - Current Time: {current_ist_datetime.strftime('%Y-%m-%d %H:%M:%S IST')}

"""
        
        if state.get("state") == "creating_task":
            system_instruction += "\nThe user is currently creating a task. Ask for missing details if needed."
        
        # 4. Call LLM
        # Note: We pass the text separately as the 'current' message, 
        # though it's also persisted. The LLM function handles formatting.
        response = chat_with_mcp(text, history, system_instruction)
        
        # Safety: If response is huge (like an HTML error dump), truncate it
        if len(response) > 4000:
            logger.error("LLM returned massive payload, likely an error page.")
            return "⚠️ System Error: The AI service returned an invalid response."
        return response
    except Exception as e:
        logger.error(f"LLM Generation failed: {e}")
        return "⚠️ AI Error: I couldn't process that."

def handle_webhook(
    body: Mapping,
    headers: Mapping[str, str],
    raw_body: Optional[bytes] = None,
    config: Optional[WhatsAppConfig] = None,
) -> Tuple[Mapping, int]:
    
    cfg = config or WhatsAppConfig()
    rb = raw_body if raw_body is not None else json.dumps(body).encode("utf-8")
    
    if not validate_signature(rb, headers, cfg.APP_SECRET):
        return {"status": "error", "message": "Invalid signature"}, 403

    db = SessionLocal()
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        if value.get("statuses"):
            return {"status": "ok"}, 200

        messages = value.get("messages")
        if not messages:
            return {"status": "ok"}, 200

        msg = messages[0]
        contacts = value.get("contacts", [])
        sender_waid = contacts[0].get("wa_id") if contacts else msg.get("from")
        
        text_body = None
        
        # Handle Text
        if msg.get("type") == "text":
            text_body = msg["text"]["body"]
            
        # Handle Audio
        elif msg.get("type") == "audio":
            logger.info("Received audio message")
            audio_id = msg["audio"]["id"]
            audio_binary = download_whatsapp_media(audio_id, cfg.ACCESS_TOKEN)
            if audio_binary:
                text_body = transcribe_audio(audio_binary)
                logger.info(f"Transcribed: {text_body}")
                # Notify user of transcription (optional, but good UX)
                # send_whatsapp_text(sender_waid, f"🎤 Transcribed: {text_body}", config=cfg)
            else:
                text_body = "Error: Could not download audio."

        if text_body:
            logger.info(f"Received from {sender_waid}: {text_body}")
            
            # Identify User
            user = get_user_by_phone(db, sender_waid)
            user_id = user.id if user else None
            
            # Get current state (for persistence)
            current_state = get_last_state(db, user_id) if user_id else {}

            # IMMEDIATE PERSISTENCE (IN)
            if user_id:
                new_msg_in = Message(
                    user_id=user_id,
                    direction=MessageDirection.in_dir,
                    channel=MessageChannel.whatsapp,
                    message_text=text_body,
                    user_state=current_state # Persist state at moment of receipt
                )
                db.add(new_msg_in)
                db.commit()
            
            # Generate Response
            if user_id:
                reply = _generate_response(user_id, text_body, db)
            else:
                reply = "Welcome! I don't recognize this phone number. Please contact support to register."

            print(f"Response generated: {reply}")

            # PERSIST RESPONSE (OUT)
            if user_id:
                # Keep state simple for MVP - always idle
                # State column exists for future use but not actively used
                new_msg_out = Message(
                    user_id=user_id,
                    direction=MessageDirection.out,
                    channel=MessageChannel.whatsapp,
                    message_text=reply,
                    user_state={"state": "idle"}  # Simple for MVP
                )
                db.add(new_msg_out)
                db.commit()

            if sender_waid:
                send_whatsapp_text(sender_waid, reply, config=cfg)
                
        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"Webhook handling error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500
    finally:
        db.close()