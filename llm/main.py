from typing import List
import openai
import time
import re
import logging
from datetime import datetime
import pytz
from .prompt import STATIC_SYSTEM_INSTRUCTION
from .config import config

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
    history: List[dict] = None, 
    user_context: dict = None,
    max_retries: int = 2
) -> str:
    """
    Chat with MCP-enabled LLM with retry logic and tool name sanitization.
    
    Args:
        prompt: User's current message
        history: Conversation history
        user_context: Context dict containing 'user_name', 'current_time', 'state', 'auth_token'
        max_retries: Number of retry attempts for failed tool calls (default: 2)
    
    Returns:
        str: LLM's response text
    """
    api_key = config.GROQ_API_KEY
    client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    # Handle None defaults
    if history is None:
        history = []
    if user_context is None:
        user_context = {}

    # Format history into a string
    history_str = ""
    for msg in history:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        history_str += f"{role}: {content}\n"

    # Construct dynamic context prompt
    auth_token = user_context.get("auth_token", "Unknown")
    user_name = user_context.get("user_name", "User")
    user_role = user_context.get("user_role", "employee")
    department = user_context.get("department", "")
    
    # Role-based permission hint
    if user_role in ["intern", "employee"]:
        role_hint = "You can only update tasks assigned to you. You cannot assign tasks to others."
    else:
        role_hint = "You can manage all tasks and assign tasks to team members."
    
    context_instruction = f"""
        === YOUR IDENTITY ===
        You are helping: {user_name} ({user_role})
        Department: {department}

        === ROLE PERMISSIONS ===
        {role_hint}

        === LANGUAGE ===
        Respond in the SAME language the user speaks (Hindi, Marathi, or English).
        Keep replies concise and friendly.

        === AUTH TOKEN (REQUIRED FOR ALL TOOLS) ===
        For EVERY tool call, pass: auth_token="{auth_token}"
    """

    # Get current time in IST
    ist_tz = pytz.timezone('Asia/Kolkata')
    current_time_ist = datetime.now(ist_tz).strftime('%Y-%m-%d %H:%M:%S')

    final_prompt = f"DateTime: {current_time_ist}\nContext: {context_instruction}\nHistory:\n{history_str}\n\nUser: {prompt}"

    kwargs = dict(
        model="openai/gpt-oss-20b",
        input=final_prompt,
        instructions=STATIC_SYSTEM_INSTRUCTION,
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
            logger.info(f"Sending prompt to LLM: {final_prompt[:200]}... [truncated]")
            
            response = client.responses.create(**kwargs)
            logger.info(f"LLM response output: {response.output}")
            
            # Sanitize tool calls to handle gpt-oss-20b corruption
            response = sanitize_tool_calls(response)
            
            # Extract text response
            for item in response.output:
                if item.type == 'message':
                    for content in item.content:
                        if content.type == 'output_text':
                            logger.info(f"LLM Final Text: {content.text}")
                            return content.text
                elif item.type == 'tool_use':
                     logger.info(f"Tool Use: {item.name} | Input: {item.input}")
                elif item.type == 'tool_result':
                     logger.info(f"Tool Result: {item.content}")
            
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
    # Example context for testing
    ctx = {"auth_token": "test-token", "state": "idle"}
    response = chat_with_mcp(user_text, user_context=ctx)
    print(response)