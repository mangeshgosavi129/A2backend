from pathlib import Path
from typing import List
import openai
from dotenv import load_dotenv
import os
import requests
import time

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

def get_mcp_ngrok_url(retries: int = 5, delay: float = 1.0) -> str:
    """Fetch the MCP ngrok public URL dynamically."""
    api_url = "http://localhost:4040/api/tunnels"

    for attempt in range(retries):
        try:
            r = requests.get(api_url).json()
            tunnels = r.get("tunnels", [])

            for t in tunnels:
                # Match based on tunnel name or port 8001
                if "mcp" in t.get("name", "").lower() or ":8001" in t.get("config", {}).get("addr", ""):
                    url = t["public_url"]
                    # Convert https://abcd.ngrok-free.app -> https://abcd.ngrok-free.app/sse
                    return url.rstrip("/") + "/sse"

        except Exception as e:
            # Try again after small delay
            time.sleep(delay)

    raise RuntimeError("MCP ngrok tunnel not found. Is ngrok running?")


def chat_with_mcp(prompt: str, history: List[dict] = [], system_instruction: str = "You are a helpful assistant.") -> str:
    api_key = os.getenv("GROQ_API_KEY")
    client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    # Fetch dynamic MCP endpoint
    mcp_url = get_mcp_ngrok_url()
    print(f"[INFO] Using MCP endpoint: {mcp_url}")

    # Format history into a string
    history_str = ""
    for msg in history:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        history_str += f"{role}: {content}\n"

    final_prompt = f"System: {system_instruction}\n\nHistory:\n{history_str}\n\nUser: {prompt}\n\nAssistant:"

    kwargs = dict(
        model="openai/gpt-oss-20b",
        input=final_prompt,
        tools=[
            {
                "type": "mcp",
                "server_label": "main backend",
                "server_url": mcp_url,
                "headers": {},
                "require_approval": "never",
                "allowed_tools": []
            }
        ],
    )

    response = client.responses.create(**kwargs)

    for item in response.output:
        if item.type == 'message':
            for content in item.content:
                if content.type == 'output_text':
                    print(content.text)
                    return content.text
    
    return "No response generated."


if __name__ == "__main__":
    user_text = "List all users"
    response = chat_with_mcp(user_text)
    print(response)