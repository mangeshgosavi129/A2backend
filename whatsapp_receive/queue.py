import boto3
import json
import logging
from typing import Mapping, Optional, Tuple
from .config import config
from .security import validate_signature

# Print config values at module load for debugging
print("=" * 50)
print("[queue.py] Loading SQS configuration...")
print(f"[queue.py] AWS_REGION: {config.AWS_REGION}")
print(f"[queue.py] AWS_ACCESS_KEY_ID: {config.AWS_ACCESS_KEY_ID[:4] + '***' if config.AWS_ACCESS_KEY_ID else 'None'}")
print(f"[queue.py] AWS_SECRET_ACCESS_KEY: {'***' if config.AWS_SECRET_ACCESS_KEY else 'None'}")
print(f"[queue.py] QUEUE_URL: {config.QUEUE_URL}")
print("=" * 50)

# Initialize SQS client outside the function for better performance (warm starts)
sqs = boto3.client(
    'sqs',
    region_name=config.AWS_REGION,
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
)
print("[queue.py] SQS client initialized successfully!")

def push_to_queue(
    body: Mapping,
    headers: Mapping[str, str],
    raw_body: Optional[bytes] = None,
) -> Tuple[Mapping, int]:
    print("-" * 40)
    print("[push_to_queue] Function called")
    print(f"[push_to_queue] Body keys: {list(body.keys()) if body else 'empty'}")
    print(f"[push_to_queue] Raw body size: {len(raw_body) if raw_body else 0} bytes")

    # if not validate_signature(raw_body, headers, config.APP_SECRET):
    #     return {"status": "error", "message": "Invalid signature"}, 403
    
    # --- SQS Logic Starts Here ---
    try:
        message_body = json.dumps(body)
        print(f"[push_to_queue] Sending message to SQS... (size: {len(message_body)} chars)")
        print(f"[push_to_queue] Queue URL: {config.QUEUE_URL}")
        
        response = sqs.send_message(
            QueueUrl=config.QUEUE_URL,
            MessageBody=message_body
        )
        
        print(f"[push_to_queue] SQS Response: MessageId={response.get('MessageId')}")
        print("[push_to_queue] Successfully pushed to SQS!")
    except Exception as e:
        print(f"[push_to_queue] ERROR: Failed to push to SQS: {str(e)}")
        logging.error(f"Failed to push to SQS: {str(e)}")
        return {"status": "error", "message": "Queue sync failed"}, 500

    print("-" * 40)
    return {"status": "ok"}, 200
