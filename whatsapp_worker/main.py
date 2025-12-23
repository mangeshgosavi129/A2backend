from whatsapp_worker.processors.apis import (store_message,get_user_details,check_idempotency)
import logging
from typing import Mapping, Tuple
from .config import config
from .processors.llm import generate_llm_response
from whatsapp_worker.send import send_whatsapp_text
from whatsapp_worker.processors.audio import process_audio_sync
import boto3
import json
import time

logger = logging.getLogger(__name__)

# --- SQS Client Initialization ---
sqs = boto3.client(
    'sqs',
    region_name=config.AWS_REGION,
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
)

def start_worker():
    """
    Infinite loop to pull messages from SQS and pass them to handle_webhook.
    """
    logger.info(f"Worker started. Listening on: {config.QUEUE_URL}")

    while True:
        try:
            # Long Polling: Wait up to 20 seconds for a message
            response = sqs.receive_message(
                QueueUrl=config.QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=30  # Message is hidden for 30s while we process
            )

            messages = response.get('Messages', [])
            if not messages:
                continue

            for message in messages:
                receipt_handle = message['ReceiptHandle']
                
                # SQS Body is a string, so we must parse it back to a Dict
                body = json.loads(message['Body'])
                
                # Execute your logic
                result_body, status_code = handle_webhook(body)

                # If successful (200), delete from queue so it's not retried
                if status_code == 200:
                    sqs.delete_message(
                        QueueUrl=config.QUEUE_URL,
                        ReceiptHandle=receipt_handle
                    )
                else:
                    logger.warning(f"Processing failed with {status_code}. Message will be retried by SQS.")

        except Exception as e:
            logger.error(f"Worker Loop Error: {e}")
            time.sleep(5) # Cooldown before retrying loop

def handle_webhook(body: Mapping) -> Tuple[Mapping, int]:
    try:
        value = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
        
        if value.get("statuses"):
            return {"status": "ok"}, 200

        messages = value.get("messages")
        if not messages:
            return {"status": "ok"}, 200

        msg = messages[0]
        whatsapp_id = msg.get("id")
        
        if check_idempotency(whatsapp_id):
            return {"status": "ok"}, 200
        
        contacts = value.get("contacts", [])
        sender_waid = contacts[0].get("wa_id") if contacts and len(contacts) > 0 else msg.get("from")
        
        text_body = None
        
        # Handle Text
        if msg.get("type") == "text":
            text_body = msg["text"]["body"]
            
        # Handle Audio
        elif msg.get("type") == "audio":
            logger.info("Received audio message")
            audio_id = msg["audio"]["id"]
            process_audio_sync(sender_waid, audio_id, whatsapp_id)
            return {"status": "ok"}, 200  # Audio handles its own response

        # Process text message
        if text_body:
            logger.info(f"Received from {sender_waid}: {text_body}")
            
            # Identify User
            user = get_user_details(phone=sender_waid)
            user_id = user.get("id") if user else None

            store_message(user_id, text_body, whatsapp_id, direction="in")
            
            # Generate Response
            if user_id:
                reply = generate_llm_response(user_id, text_body)
            else:
                reply = "Welcome! I don't recognize this phone number. Please contact support to register."

            logger.info(f"Response generated: {reply}")

            store_message(user_id, reply, whatsapp_id, direction="out")

            if sender_waid:
                send_whatsapp_text(sender_waid, reply)
                
        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"Webhook handling error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


if __name__ == "__main__":
    start_worker()

