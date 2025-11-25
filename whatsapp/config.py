import os
import logging
from dotenv import load_dotenv
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

current_file_path = Path(__file__).resolve()
whatsapp_dir = current_file_path.parent  # .../Archive/whatsapp
local_env = whatsapp_dir / ".env"        # .../Archive/whatsapp/.env

print(f"DEBUG: WhatsApp Config initializing...")
print(f"DEBUG: Target .env path: {local_env}")

if local_env.exists():
    print(f"DEBUG: Found local .env! Loading variables...")
    load_dotenv(dotenv_path=local_env, override=True)
else:
    print(f"DEBUG: ❌ .env file NOT found at {local_env}")

class WhatsAppConfig:
    def __init__(
        self,
        access_token: Optional[str] = None,
        version: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        verify_token: Optional[str] = None,
        app_secret: Optional[str] = None,
        default_recipient_waid: Optional[str] = None,
    ) -> None:
        self.ACCESS_TOKEN = access_token or os.getenv("ACCESS_TOKEN")
        self.VERSION = version or os.getenv("VERSION")
        self.PHONE_NUMBER_ID = phone_number_id or os.getenv("PHONE_NUMBER_ID")
        self.VERIFY_TOKEN = verify_token or os.getenv("VERIFY_TOKEN")
        self.APP_SECRET = app_secret or os.getenv("APP_SECRET")
        self.RECIPIENT_WAID = default_recipient_waid or os.getenv("RECIPIENT_WAID")

        missing = []
        if not self.ACCESS_TOKEN: missing.append("ACCESS_TOKEN")
        if not self.PHONE_NUMBER_ID: missing.append("PHONE_NUMBER_ID")
        
        if missing:
            print(f"⚠️  CRITICAL CONFIG ERROR: Missing values for {', '.join(missing)}")
            if local_env.exists():
                try:
                    with open(local_env, 'r') as f:
                        print(f"    File preview: {f.read(50)}...")
                except Exception as e:
                    print(f"    Error reading file: {e}")