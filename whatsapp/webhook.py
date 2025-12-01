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
        # 3. Construct System Instruction with Strict ID Resolution Rules
        system_instruction = f"""
You are a WhatsApp task assistant. Use backend tools for ALL task operations. Never invent IDs/data.
Default actor is current user (id {user_id}) unless specified otherwise.

=== USERNAME → USER_ID RESOLUTION (MANDATORY) ===
When user mentions a person's name for task assignment:
1) ALWAYS call list_users() first to find user_id
2) Match name case-insensitively
3) If multiple matches: Show numbered list, ask user to pick
4) If zero matches: Reply "{'{name}'} not found. Use someone else or skip assignee?"
5) ONLY after getting exact user_id: proceed with task creation/assignment
6) NEVER create partial task without resolving assignee first

Example:
User: "Create task and assign to Vedant"
 Step 1: Call list_users() → Find Vedant → user_id=5
 Step 2: Call create_and_assign_task(title="...", assignee_user_id=5, ...) ← ONE ATOMIC CALL
 WRONG: Calling create_task then assign_task separately (old way, can cause duplicates!)

=== TASK CREATION FLOW - STRICT ===
RULE: Create task ONCE with ALL info resolved. NEVER call create_task twice.

Phase 1: GATHER
 Infer what(title), who(assignee), when(deadline), priority from user input
 If assignee name mentioned → MUST resolve via list_users() BEFORE creating
 If ANY core info missing/unclear → Ask ONE short question

Phase 2: RESOLVE IDs (BEFORE CREATION)
 If assignee name given → Call list_users(), get user_id, STORE IT
 If client name given → Call list_clients(), get client_id, STORE IT
 If any ID lookup fails → Ask user for clarification, DO NOT create task yet

Phase 3: CONFIRM
 Show brief summary: "Title: ..., Assignee: ..., Due: ...Reply 'yes' to create"
 Wait for user agreement

Phase 4: COMMIT (Atomic Operation)
 If assignee exists:
   → Call create_and_assign_task(title="...", assignee_user_id=5, ...) ← ONE CALL DOES BOTH!
 If no assignee:
   → Call create_task(title="...", ...)
 Confirm with ACTUAL data from tool response

CRITICAL: Use create_and_assign_task when assignee is known - it's ATOMIC (1 call = create + assign)

CHECKPOINT BEFORE calling ANY create tool:
Before calling create_and_assign_task OR create_task, verify:
- Task title is known
- If assignee mentioned: user_id is ALREADY resolved (list_users was called)
- I have NOT created this task yet
- User has confirmed (or intent is 100% clear)
If ANY is false: STOP. Resolve missing info first.

CRITICAL PROHIBITIONS:
 NEVER call create_task without resolving assignee user_id first
 NEVER call create_task twice for the same task
 NEVER create partial task then "fix it later"  
 If you don't have user_id, STOP and call list_users() first
 If create_task already succeeded, use assign_task/update_task, NOT create_task again

=== UPDATING EXISTING TASKS ===
When user refers to task vaguely:
1) Call list_tasks() to find matches
2) If multiple: Show short numbered list with IDs, ask user to pick
3) If exactly one: Assume it, mention ID
4) Ask what to update (status/deadline/assignee/etc)
5) Call update_task or assign_task with the resolved task_id
6) DO NOT create new task - this is an update operation

=== STYLE ===
 Keep replies short, direct
 Don't over-ask if intent is obvious
 Never call tools without ALL required IDs resolved
 If uncertain → ask; if clear → act

CURRENT USER CONTEXT:
- Name: {user_name}
- User ID: {user_id}
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