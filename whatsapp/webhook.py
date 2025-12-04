import logging
import json
import requests
import os
from datetime import datetime
import pytz
from typing import Mapping, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
import threading
from .security import validate_signature
from .config import WhatsAppConfig
from .client import send_whatsapp_text
from .database import SessionLocal, User, Message, MessageDirection, MessageChannel
from sarvamai import SarvamAI
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

def transcribe_sarvam_audio(audio_binary: bytes) -> str:
    """Transcribe audio using Sarvam AI API with automatic batch processing fallback.
    
    For audio ≤30 seconds: Uses REST API
    For audio >30 seconds: Falls back to batch processing API
    
    Args:
        audio_binary: Audio file binary data in OGG format from WhatsApp
        
    Returns:
        Transcribed text or error message
    """
    import tempfile
    
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        logger.error("SARVAM_API_KEY not set")
        return "Error: Transcription service not configured."

    # First, try the REST API (works for audio ≤30 seconds)
    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": api_key}
    
    files = {
        'file': ('audio.ogg', audio_binary, 'audio/ogg')
    }
    data = {
        'model': 'saarika:v2.5'
    }
    
    try:
        resp = requests.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()
        result = resp.json()
        transcript = result.get("transcript", "")
        logger.info("Sarvam REST API transcription successful")
        return transcript
    except requests.exceptions.HTTPError as http_err:
        # If REST API fails (likely due to >30 second audio), fall back to batch processing
        logger.warning(f"REST API failed (likely audio >30s): {http_err}. Falling back to batch processing...")
        
        temp_audio_file = None
        temp_output_dir = None
        
        try:
            # Save audio binary to a temporary file for batch upload
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                temp_file.write(audio_binary)
                temp_audio_file = temp_file.name
            
            logger.info(f"Saved audio to temporary file: {temp_audio_file}")
            
            # Initialize Sarvam batch client
            client = SarvamAI(api_subscription_key=api_key)

            # Create and configure batch STT job
            job = client.speech_to_text_job.create_job(
                language_code="en-IN",
                model="saarika:v2.5",
                with_diarization=False,
                num_speakers=1
            )
            logger.info("Created batch transcription job")

            # Upload the audio file
            job.upload_files(file_paths=[temp_audio_file])
            logger.info("Uploaded audio file for batch processing")
            
            # Start processing
            job.start()
            logger.info("Started batch processing job")

            # Wait for completion
            job.wait_until_complete()
            logger.info("Batch processing complete")

            # Check file-level results
            file_results = job.get_file_results()

            if len(file_results['successful']) == 0:
                logger.error("Batch processing failed for all files")
                if file_results['failed']:
                    error_msg = file_results['failed'][0].get('error_message', 'Unknown error')
                    logger.error(f"Batch error: {error_msg}")
                return "Error: Batch transcription failed."

            # Download outputs to temporary directory
            temp_output_dir = tempfile.mkdtemp()
            job.download_outputs(output_dir=temp_output_dir)
            logger.info(f"Downloaded batch results to: {temp_output_dir}")

            # Extract transcript from the downloaded results
            # The output is typically a JSON file with the transcription
            import glob
            output_files = glob.glob(os.path.join(temp_output_dir, "*.json"))
            
            if not output_files:
                logger.error("No output files found in batch results")
                return "Error: Could not find transcription output."
            
            # Read the first output file (we only uploaded one audio file)
            with open(output_files[0], 'r', encoding='utf-8') as f:
                batch_result = json.load(f)
            
            # Extract transcript text from batch result
            # The structure may vary, but typically it's in 'transcript' or similar field
            transcript = batch_result.get("transcript", "")
            if not transcript:
                # Try alternative structures
                transcript = batch_result.get("text", "")
            
            if not transcript:
                logger.error(f"Could not extract transcript from batch result: {batch_result}")
                return "Error: Could not extract transcript from batch processing."
            
            logger.info(f"Batch transcription successful: {transcript[:100]}...")
            return transcript
            
        except Exception as batch_error:
            logger.error(f"Batch processing failed: {batch_error}", exc_info=True)
            return "Error: Batch transcription failed."
        
        finally:
            # Clean up temporary files
            if temp_audio_file and os.path.exists(temp_audio_file):
                try:
                    os.remove(temp_audio_file)
                    logger.info(f"Cleaned up temp audio file: {temp_audio_file}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {temp_audio_file}: {e}")
            
            if temp_output_dir and os.path.exists(temp_output_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_output_dir)
                    logger.info(f"Cleaned up temp output dir: {temp_output_dir}")
                except Exception as e:
                    logger.warning(f"Could not delete temp dir {temp_output_dir}: {e}")
    
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        return "Error: Could not transcribe audio."

def transcribe_groq_audio(audio_binary: bytes) -> str:
    """Transcribe audio using Groq's Whisper API.
    
    Args:
        audio_binary: Audio file binary data in OGG format from WhatsApp
        
    Returns:
        Transcribed text or error message
    """
    import os
    import tempfile
    from groq import Groq

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Create a temporary file with .ogg extension for WhatsApp audio
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_file.write(audio_binary)
            temp_filename = temp_file.name
        
        try:
            # Open and send the file to Groq
            with open(temp_filename, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    file=("audio.ogg", audio_file.read()),
                    model="whisper-large-v3",
                    temperature=0,
                    response_format="verbose_json",
                )
                logger.info(f"Groq transcription successful: {transcription.text}")
                return transcription.text
        finally:
            # Clean up temporary file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
    except Exception as e:
        logger.error(f"Groq transcription failed: {e}", exc_info=True)
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
            Default actor is current user (id user_id) unless specified otherwise.

            === USERNAME → USER_ID RESOLUTION (MANDATORY) ===
            When user mentions a person's name for task assignment:
            1) ALWAYS call list_users() first to find user_id
            2) Match name case-insensitively
            3) If multiple matches: Show numbered list, ask user to pick
            4) If zero matches: Reply "'Name' not found. Use someone else or skip assignee?"
            5) ONLY after getting exact user_id: proceed with task creation/assignment
            6) NEVER create partial task without resolving assignee first

            Example:
            User: "Create task and assign to Vedant"
            Step 1: Call list_users() -> Find Vedant -> user_id=5
            Step 2: Call create_and_assign_task(title="...", assignee_user_id=5, ...) <- ONE ATOMIC CALL
            WRONG: Calling create_task then assign_task separately (old way, can cause duplicates!)

            === TASK CREATION FLOW - STRICT ===
            RULE: Create task ONCE with ALL info resolved. NEVER call create_task twice.

            Phase 1: GATHER
            Infer what(title), who(assignee), when(deadline), priority from user input
            If assignee name mentioned → MUST resolve via list_users() BEFORE creating
            If ANY core info missing/unclear → Ask ONE short question

            Phase 2: RESOLVE IDs (BEFORE CREATION)
            If assignee name given -> Call list_users(), get user_id, STORE IT
            If client name given -> Call list_clients(), get client_id, STORE IT
            If any ID lookup fails -> Ask user for clarification, DO NOT create task yet

            Phase 3: CONFIRM
            Show brief summary: "Title: ..., Assignee: ..., Due: ...Reply 'yes' to create"
            Wait for user agreement

            Phase 4: COMMIT (Atomic Operation)
            If assignee exists:
            -> Call create_and_assign_task(title="...", assignee_user_id=5, ...) <- ONE CALL DOES BOTH!
            If no assignee:
            -> Call create_task(title="...", ...)
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
            If uncertain -> ask; if clear -> act

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

def process_audio_async(
    sender_waid: str,
    audio_binary: bytes,
    user_id: int,
    whatsapp_id: str,
    current_state: dict,
    config: WhatsAppConfig
):
    """
    Process audio transcription and LLM response in background thread.
    This prevents webhook timeout for long audio messages.
    """
    db = SessionLocal()
    try:
        # Transcribe audio using Groq
        logger.info("Starting audio transcription in background with Groq...")
        text_body = transcribe_sarvam_audio(audio_binary)
        logger.info(f"Transcribed: {text_body}")
        
        if text_body.startswith("Error:"):
            # Transcription failed
            send_whatsapp_text(sender_waid, text_body, config=config)
            return
        
        # Persist incoming message
        new_msg_in = Message(
            user_id=user_id,
            direction=MessageDirection.in_dir,
            channel=MessageChannel.whatsapp,
            message_text=text_body,
            user_state=current_state,
            payload={"whatsapp_id": whatsapp_id, "source": "audio"}
        )
        db.add(new_msg_in)
        db.commit()
        
        # Generate response
        reply = _generate_response(user_id, text_body, db)
        logger.info(f"Generated response: {reply}")
        
        # Persist outgoing message
        new_msg_out = Message(
            user_id=user_id,
            direction=MessageDirection.out,
            channel=MessageChannel.whatsapp,
            message_text=reply,
            user_state={"state": "idle"}
        )
        db.add(new_msg_out)
        db.commit()
        
        # Send response to user
        send_whatsapp_text(sender_waid, reply, config=config)
        logger.info("Audio processing complete and response sent.")
        
    except Exception as e:
        logger.error(f"Error in async audio processing: {e}", exc_info=True)
        error_msg = "⚠️ Sorry, I encountered an error processing your audio message."
        send_whatsapp_text(sender_waid, error_msg, config=config)
    finally:
        db.close()

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
        whatsapp_id = msg.get("id")
        
        # IDEMPOTENCY CHECK
        # Check if we've already processed this message ID
        # We store the WhatsApp ID in the 'payload' JSONB column
        if whatsapp_id:
            existing_message = db.query(Message).filter(
                Message.payload['whatsapp_id'].astext == whatsapp_id
            ).first()

            if existing_message:
                logger.warning(f"Duplicate webhook received for message ID {whatsapp_id}. Skipping.")
                return {"status": "ok"}, 200

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
            
            if not audio_binary:
                text_body = "Error: Could not download audio."
                # Process error immediately
            else:
                # Send immediate acknowledgment
                send_whatsapp_text(sender_waid, "🎤 Processing your audio message...", config=cfg)
                
                # Get user for async processing
                user = get_user_by_phone(db, sender_waid)
                if user:
                    user_id = user.id
                    current_state = get_last_state(db, user_id)
                    
                    # Process audio in background thread to avoid webhook timeout
                    thread = threading.Thread(
                        target=process_audio_async,
                        args=(sender_waid, audio_binary, user_id, whatsapp_id, current_state, cfg),
                        daemon=True
                    )
                    thread.start()
                    logger.info("Audio processing started in background thread")
                    
                    # Return immediately to avoid webhook timeout
                    return {"status": "processing"}, 200
                else:
                    text_body = "Welcome! I don't recognize this phone number. Please contact support to register."
                    # Will be processed below

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
                    user_state=current_state, # Persist state at moment of receipt
                    payload={"whatsapp_id": whatsapp_id} if whatsapp_id else None # Store WhatsApp ID for idempotency
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