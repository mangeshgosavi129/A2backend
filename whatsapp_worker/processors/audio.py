"""
Audio transcription and processing for WhatsApp messages.
"""
import logging
import requests
import json
from typing import Optional
from sarvamai import SarvamAI
from ..config import config
from .apis import get_user_details, store_message
from .llm import generate_llm_response
from ..send import send_whatsapp_text
import tempfile
import io
from pathlib import Path

logger = logging.getLogger(__name__)


def download_whatsapp_media(media_id: str, access_token: str) -> Optional[bytes]:
    """
    Download media from WhatsApp servers.
    
    Args:
        media_id: The WhatsApp media ID
        access_token: WhatsApp API access token
        
    Returns:
        Binary content of media or None on failure
    """
    try:
        url = f"https://graph.facebook.com/v22.0/{media_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        media_url = resp.json().get("url")
        
        if not media_url:
            logger.error("No media URL found in response")
            return None

        media_resp = requests.get(media_url, headers=headers, timeout=30)
        media_resp.raise_for_status()
        return media_resp.content
    except requests.RequestException as e:
        logger.error(f"Failed to download media: {e}")
        return None


def transcribe_sarvam_audio(audio_binary: bytes) -> str:
    """
    Transcribe audio using Sarvam AI.
    Tries real-time API first, falls back to batch for long audio.
    
    Args:
        audio_binary: Raw audio bytes (OGG format)
        
    Returns:
        Transcribed text or error message starting with "Error:"
    """
    api_key = config.SARVAM_API_KEY
    if not api_key:
        return "Error: Transcription service not configured."

    # 1. Attempt Real-time REST API
    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": api_key}
    files = {'file': ('audio.ogg', io.BytesIO(audio_binary), 'audio/ogg')}
    data = {'model': 'saarika:v2.5', 'input_audio_codec': 'ogg'}

    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=35)
        resp.raise_for_status()
        return resp.json().get("transcript", "")

    except requests.exceptions.HTTPError as e:
        # Fallback only on size/duration limits (413 or 400)
        if e.response.status_code not in [400, 413]:
            logger.error(f"REST API failed: {e}")
            return f"Error: Transcription failed - {e}"
        logger.info("Audio >30s or too large. Falling back to Batch API...")

    # 2. Batch Processing Fallback for long audio
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.ogg"
            input_file.write_bytes(audio_binary)

            client = SarvamAI(api_subscription_key=api_key)
            job = client.speech_to_text_job.create_job(
                language_code="en-IN",
                model="saarika:v2.5",
                with_diarization=False
            )
            
            job.upload_files(file_paths=[str(input_file)])
            job.start()
            job.wait_until_complete()
            
            # Check results before downloading
            file_results = job.get_file_results()
            if not file_results.get('successful'):
                error = file_results.get('failed', [{}])[0].get('error_message', 'Unknown')
                return f"Error: Batch failure - {error}"

            # Download and parse results
            output_dir = temp_path / "output"
            output_dir.mkdir()
            job.download_outputs(output_dir=str(output_dir))
            
            result_file = next(output_dir.rglob("*.json"), None)
            if not result_file:
                return "Error: No output JSON found."

            batch_data = json.loads(result_file.read_text(encoding='utf-8'))
            return batch_data.get("transcript") or batch_data.get("text") or ""

    except Exception as e:
        logger.exception("Sarvam Batch Processing failed")
        return f"Error: {str(e)}"


def process_audio_sync(sender_waid: str, audio_id: str, whatsapp_id: str) -> None:
    """
    Process audio message: download, transcribe, generate response, and send.
    
    Args:
        sender_waid: Sender's WhatsApp ID (phone number)
        audio_id: WhatsApp media ID for the audio
        whatsapp_id: Unique WhatsApp message ID for idempotency
    """
    # Download audio
    audio_binary = download_whatsapp_media(audio_id, config.ACCESS_TOKEN)
    
    if not audio_binary:
        send_whatsapp_text(sender_waid, "⚠️ Error: Could not download audio.")
        return
    
    # Look up user
    user = get_user_details(phone=sender_waid)
    if not user:
        send_whatsapp_text(
            sender_waid,
            "Welcome! I don't recognize this phone number. Please contact support to register."
        )
        return
    
    user_id = user.get("id")
    
    try:
        # Transcribe audio
        text_body = transcribe_sarvam_audio(audio_binary)
        
        if text_body.startswith("Error:"):
            send_whatsapp_text(sender_waid, text_body)
            return
        
        if not text_body.strip():
            send_whatsapp_text(sender_waid, "⚠️ I couldn't hear anything in your audio message.")
            return
        
        logger.info(f"Transcribed audio from {sender_waid}: {text_body[:100]}...")
        
        # Store incoming transcription
        store_message(user_id, text_body, whatsapp_id, direction="in")
        
        # Generate LLM response
        reply = generate_llm_response(user_id, text_body)
        
        # Store outgoing response
        store_message(user_id, reply, whatsapp_id, direction="out")
        
        # Send reply
        send_whatsapp_text(sender_waid, reply)
        
    except Exception as e:
        logger.error(f"Error in audio processing: {e}", exc_info=True)
        send_whatsapp_text(
            sender_waid,
            "⚠️ Sorry, I encountered an error processing your audio message."
        )
