import logging
from datetime import timedelta
from .apis import get_user_details, get_chat_history
from llm.main import chat_with_mcp
from server.security import create_access_token

logger = logging.getLogger(__name__)

def generate_llm_response(user_id: int, text: str) -> str:
    try:
        user = get_user_details(user_id=user_id, include_role=True)
        if not user:
            logger.error(f"User {user_id} not found for LLM processing")
            return "⚠️ Error: User not found."
        
        user_name = user.get("name", "User")
        user_dept = user.get("department") or "N/A"
        org_id = user.get("org_id")
        
        user_role_str = user.get("role", "intern") if user else "intern"
        
        history = get_chat_history(user_id)
        
        # Short-lived token for LLM tool calls
        auth_token = create_access_token(
            data={"sub": str(user_id), "org_id": org_id},
            expires_delta=timedelta(minutes=5)
        )
        
        user_context = {
            "user_name": user_name,
            "user_role": user_role_str,
            "department": user_dept,
            "auth_token": auth_token
        }
        
        response = chat_with_mcp(text, history, user_context=user_context)
        
        if len(response) > 4000:
            logger.error("LLM returned massive payload, likely an error page.")
            return "⚠️ System Error: The AI service returned an invalid response."

        return response

    except Exception as e:
        logger.error(f"LLM Generation failed: {e}", exc_info=True)
        return "⚠️ AI Error: I couldn't process that."
