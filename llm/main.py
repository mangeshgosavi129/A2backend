from pathlib import Path
from typing import List
import openai
from dotenv import load_dotenv
import os
import time
import re
import logging
from datetime import datetime
import pytz

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

STATIC_SYSTEM_INSTRUCTION = """
You are a WhatsApp task assistant. Use backend tools for ALL task operations. Never invent IDs/data.

=== USERNAME -> USER_ID RESOLUTION (MANDATORY) ===
When user mentions a person's name for task assignment:
1 ALWAYS call list_users() first to find user_id
2 Match name case-insensitively
3 If multiple matches: Show numbered list, ask user to pick
4 If zero matches: Reply "'Name' not found. Use someone else or skip assignee?"
5 ONLY after getting exact user_id: proceed with task creation/assignment
6 NEVER create partial task without resolving assignee first

Example:
User: "Create task and assign to Vedant"
Step 1: Call list_users() -> Find Vedant -> user_id=5
Step 2: Call create_and_assign_task(title="...", assignee_user_id=5, ...) <- ONE ATOMIC CALL

=== TASK CREATION FLOW - STRICT ===
RULE: Create task ONCE with ALL info resolved. NEVER call create_task twice.

Phase 1: GATHER
Infer what(title), who(assignee), when(deadline), priority from user input
If assignee name mentioned -> MUST resolve via list_users() BEFORE creating
If ANY core info missing/unclear -> Ask ONE short question

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
- User has confirmed (or intent is 100 percent clear)
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

CRITICAL TOOL USAGE RULES:
Always use the exact tool names provided
Double-check all required parameters before calling tools
If a parameter can be null/None, you may omit it or pass null
Never hallucinate tool names or parameters
"""

def chat_with_mcp(
    prompt: str, 
    history: List[dict] = [], 
    user_context: dict = {},
    max_retries: int = 2
) -> str:
    """
    Chat with MCP-enabled LLM with retry logic and tool name sanitization.
    
    Args:
        prompt: User's current message
        history: Conversation history
        user_context: Context dict containing 'user_id', 'org_id', 'user_name', 'current_time', 'state'
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

    # Construct dynamic context prompt
    user_id = user_context.get("user_id", "Unknown")
    org_id = user_context.get("org_id", "Unknown")
    
    context_instruction = f"""
    Default actor is current user (id {user_id}).
    Current Organisation ID: {org_id}

    === CRITICAL AUTHENTICATION RULE ===
    For EVERY tool call, you MUST pass these two parameters to identify the user:
    - `requesting_user_id`: {user_id}
    - `requesting_org_id`: {org_id}

    Example: create_task(title="...", requesting_user_id={user_id}, requesting_org_id={org_id})
    FAILURE TO PASS THESE will result in actions being performed as the wrong user/org!
    """

    # Get current time in IST
    ist_tz = pytz.timezone('Asia/Kolkata')
    current_time_ist = datetime.now(ist_tz).strftime('%Y-%m-%d %H:%M:%S')

    final_prompt = f"DateTime: {current_time_ist}\nContext: {context_instruction}\nHistory:\n{history_str}\n\nUser: {prompt}"

    if user_context.get("state") == "creating_task":
        context_instruction += "\nThe user is currently creating a task. Ask for missing details if needed.\n"

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
    # Example context for testing
    ctx = {"user_id": 1, "org_id": 1, "state": "idle"}
    response = chat_with_mcp(user_text, user_context=ctx)
    print(response)