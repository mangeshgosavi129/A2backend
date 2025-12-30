import os
from pathlib import Path
from dotenv import load_dotenv

# Load from .env.dev for local development
current_file_path = Path(__file__).resolve()
root_dir = current_file_path.parent.parent
env_path = root_dir / ".env.dev"

if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"[whatsapp_receive/config.py] Loaded env from: {env_path}")
else:
    load_dotenv()  # Fall back to Lambda environment
    print(f"[whatsapp_receive/config.py] Warning: .env.dev not found at {env_path}, using system env")

class WhatsAppReceiveConfig:
    def __init__(self) -> None:
        self.VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
        self.APP_SECRET = os.getenv("APP_SECRET")
        self.ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
        self.VERSION = os.getenv("VERSION")
        self.PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
        self.QUEUE_URL = os.getenv("QUEUE_URL")
        self.AWS_REGION = os.getenv("AWS_REGION")
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

config = WhatsAppReceiveConfig()