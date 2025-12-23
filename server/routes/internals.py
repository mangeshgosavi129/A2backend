from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from server.models import User, Message, UserRole
from server.enums import MessageDirection, MessageChannel, Role
from server.schemas import MessageCreate, MessageResponse
from server.dependencies import get_db

router = APIRouter()

# =========================================================
# INTERNAL ENDPOINTS (No Authentication Required)
# Used by whatsapp_worker for backend operations
# =========================================================

@router.get("/user")
def get_user(
    phone: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    include_role: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Lookup user by phone or id. Optionally include role."""
    user = None
    
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    elif phone:
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            if phone.startswith("+"):
                user = db.query(User).filter(User.phone == phone[1:]).first()
            else:
                user = db.query(User).filter(User.phone == f"+{phone}").first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    result = {
        "id": user.id,
        "org_id": user.org_id,
        "name": user.name,
        "phone": user.phone,
        "department": user.department
    }
    
    if include_role:
        user_role = db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.org_id == user.org_id
        ).first()
        result["role"] = user_role.role.value if user_role else Role.intern.value
    
    return result


@router.get("/idempotency/{whatsapp_id}")
def check_msg_exists(whatsapp_id: str, db: Session = Depends(get_db)):
    """Check if WhatsApp message already processed (idempotency)."""
    existing = db.query(Message).filter(
        Message.payload['whatsapp_id'].astext == whatsapp_id
    ).first()
    return {"exists": existing is not None}


@router.post("/message", response_model=MessageResponse)
def store_msg(message_data: MessageCreate, db: Session = Depends(get_db)):
    """Store a message. Auto-determines org_id from user."""
    org_id = None
    if message_data.user_id:
        user = db.query(User).filter(User.id == message_data.user_id).first()
        if user:
            org_id = user.org_id
    
    if org_id is None:
        org_id = 1
    
    message = Message(
        org_id=org_id,
        user_id=message_data.user_id,
        task_id=message_data.task_id,
        direction=message_data.direction,
        channel=message_data.channel,
        message_text=message_data.message_text,
        payload=message_data.payload
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/history/{user_id}")
def get_history(
    user_id: int,
    limit: int = Query(default=15, le=50),
    db: Session = Depends(get_db)
):
    """Get chat history for LLM context."""
    messages = db.query(Message).filter(
        Message.user_id == user_id,
        Message.channel == MessageChannel.whatsapp
    ).order_by(desc(Message.created_at)).limit(limit).all()
    
    messages.reverse()
    
    history = []
    for msg in messages:
        role = "user" if msg.direction == MessageDirection.in_dir else "assistant"
        history.append({"role": role, "content": msg.message_text or ""})
    
    return history
