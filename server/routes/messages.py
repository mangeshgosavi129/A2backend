from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from server.schemas import MessageResponse, MessageCreate, MessageDirection, MessageChannel
from server.models import Message, User
from server.dependencies import get_db, get_current_user

router = APIRouter()

# =========================================================
# MESSAGE ENDPOINTS
# =========================================================
@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def create_message(
    message_data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Auto-set org_id from current user
    message = Message(**message_data.dict(), org_id=current_user.org_id)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message

@router.get("/messages", response_model=List[MessageResponse])
def get_messages(
    user_id: Optional[int] = Query(None),
    task_id: Optional[int] = Query(None),
    direction: Optional[MessageDirection] = Query(None),
    channel: Optional[MessageChannel] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Filter by org_id for tenant isolation
    query = db.query(Message).filter(Message.org_id == current_user.org_id)
    
    if user_id is not None:
        query = query.filter(Message.user_id == user_id)
    if task_id is not None:
        query = query.filter(Message.task_id == task_id)
    if direction is not None:
        query = query.filter(Message.direction == direction)
    if channel is not None:
        query = query.filter(Message.channel == channel)
    
    messages = query.all()
    return messages