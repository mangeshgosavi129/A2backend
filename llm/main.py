from pathlib import Path
from typing import List
import openai
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

def chat_with_mcp(prompt: str, history: List[dict] = [], system_instruction: str = "You are a helpful assistant.") -> str:
    api_key = os.getenv("GROQ_API_KEY")
    client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

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
                "server_url": "https://mcp.graphsensesolutions.com/sse",
                "headers": {},
                "require_approval": "never"
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