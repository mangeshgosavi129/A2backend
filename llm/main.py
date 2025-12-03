from pathlib import Path
from typing import List
import openai
from dotenv import load_dotenv
import os
import time
import re
import logging

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sanitize_tool_calls(response_data: dict) -> dict:
    """
    Sanitize tool calls to remove corrupted tokens like <|channel|>commentary.
    This works around gpt-oss-20b's tendency to append special tokens to tool names.
    """
    if not hasattr(response_data, 'output'):
        return response_data
    
    # Pattern to match corrupted suffixes
    # Matches: <|channel|>commentary, <|xyz|>anything, etc.
    corruption_pattern = r'<\|[^|]+\|>[a-z_]+'
    
    for item in response_data.output:
        if item.type == 'tool_use':
            original_name = item.name
            # Strip any <|*|>* suffix from tool name
            cleaned_name = re.sub(corruption_pattern, '', item.name)
            if cleaned_name != original_name:
                logger.warning(f"Sanitized corrupted tool name: '{original_name}' -> '{cleaned_name}'")
                item.name = cleaned_name
    
    return response_data

def chat_with_mcp(
    prompt: str, 
    history: List[dict] = [], 
    system_instruction: str = "You are a helpful assistant.",
    max_retries: int = 2
) -> str:
    """
    Chat with MCP-enabled LLM with retry logic and tool name sanitization.
    
    Args:
        prompt: User's current message
        history: Conversation history
        system_instruction: System prompt for the LLM
        max_retries: Number of retry attempts for failed tool calls (default: 2)
    
    Returns:
        str: LLM's response text
    """
    api_key = os.getenv("GROQ_API_KEY")
    client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    # Format history into a string
    history_str = ""
    for msg in history:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        history_str += f"{role}: {content}\n"

    final_prompt = f"History:\n{history_str}\n\nUser: {prompt}"
    
    # Enhanced system instruction for better tool calling with gpt-oss-20b
    enhanced_instruction = f"""{system_instruction}

CRITICAL TOOL USAGE RULES:
- Always use the exact tool names provided
- Double-check all required parameters before calling tools
- If a parameter can be null/None, you may omit it or pass null
- Never hallucinate tool names or parameters
"""

    kwargs = dict(
        model="openai/gpt-oss-20b",
        input=final_prompt,
        instructions=enhanced_instruction,
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

    # Retry loop with exponential backoff
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"LLM request attempt {attempt + 1}/{max_retries + 1}")
            
            response = client.responses.create(**kwargs)
            logger.info(f"LLM response: {response}")
            # Sanitize tool calls to handle gpt-oss-20b corruption
            response = sanitize_tool_calls(response)
            
            # Extract text response
            for item in response.output:
                if item.type == 'message':
                    for content in item.content:
                        if content.type == 'output_text':
                            logger.info(f"LLM response successful on attempt {attempt + 1}")
                            return content.text
            
            return "No response generated."
            
        except Exception as e:
            error_msg = str(e)
            last_error = e
            
            # Check if it's a recoverable tool call error
            is_tool_error = any(keyword in error_msg.lower() for keyword in [
                'tool call validation failed',
                'tool_use_failed',
                'invalid_request_error'
            ])
            
            if is_tool_error and attempt < max_retries:
                backoff_time = 0.5 * (attempt + 1)
                logger.warning(
                    f"Tool call failed on attempt {attempt + 1}/{max_retries + 1}: {error_msg}. "
                    f"Retrying in {backoff_time}s..."
                )
                time.sleep(backoff_time)
                continue
            else:
                # Non-recoverable error or out of retries
                logger.error(f"LLM request failed after {attempt + 1} attempts: {error_msg}")
                raise
    
    # Should not reach here, but just in case
    raise last_error if last_error else Exception("Unknown error in chat_with_mcp")


if __name__ == "__main__":
    user_text = "List all users"
    response = chat_with_mcp(user_text)
    print(response)