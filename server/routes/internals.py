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


@router.get("/tasks-with-deadlines")
def get_tasks_with_deadlines(db: Session = Depends(get_db)):
    """
    Fetch all active tasks with deadlines for the reminder scheduler.
    Returns tasks that are not completed/cancelled and have a deadline set.
    Only fetches tasks within a relevant time window (24h past to 2h future).
    """
    from server.models import Task, TaskAssignee
    from server.enums import TaskStatus
    from datetime import datetime, timedelta
    
    # Only fetch tasks with deadlines within a reasonable window
    now = datetime.utcnow()
    window_start = now - timedelta(hours=24)  # Include overdue up to 24h
    window_end = now + timedelta(hours=2)     # 2 hour lookahead
    
    tasks = db.query(Task).filter(
        Task.deadline.isnot(None),
        Task.deadline >= window_start,
        Task.deadline <= window_end,
        Task.status.notin_([TaskStatus.completed, TaskStatus.cancelled])
    ).all()
    
    result = []
    for task in tasks:
        # Get active assignees with phone numbers
        active_assignees = db.query(TaskAssignee).filter(
            TaskAssignee.task_id == task.id,
            TaskAssignee.unassigned_at.is_(None)
        ).all()
        
        assignees = []
        for a in active_assignees:
            if a.user and a.user.phone:
                assignees.append({
                    'user_id': a.user_id,
                    'name': a.user.name,
                    'phone': a.user.phone
                })
        
        if assignees:  # Only include tasks with at least one assignee
            result.append({
                'id': task.id,
                'title': task.title,
                'deadline': task.deadline.isoformat() if task.deadline else None,
                'status': task.status.value,
                'assignees': assignees
            })
    
    return result


@router.get("/daily-personal-report/{user_id}")
def get_daily_personal_report(user_id: int, db: Session = Depends(get_db)):
    """
    Get data for personal daily report.
    Returns: completed tasks today, due tasks, user's progress updates today.
    """
    from server.models import Task, TaskAssignee, User
    from server.enums import TaskStatus
    from datetime import datetime, timedelta
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    
    # Today's date range (IST)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # 1. Tasks marked completed today (that user is assigned to)
    completed_today = []
    user_assignments = db.query(TaskAssignee).filter(
        TaskAssignee.user_id == user_id,
        TaskAssignee.unassigned_at.is_(None)
    ).all()
    
    for assignment in user_assignments:
        task = assignment.task
        if task.status == TaskStatus.completed and task.updated_at >= today_start:
            completed_today.append({
                'id': task.id,
                'title': task.title,
                'completed_at': task.updated_at.isoformat() if task.updated_at else None
            })
    
    # 2. Due tasks (not completed, not cancelled) sorted by deadline
    due_tasks = []
    for assignment in user_assignments:
        task = assignment.task
        if task.status not in [TaskStatus.completed, TaskStatus.cancelled]:
            due_tasks.append({
                'id': task.id,
                'title': task.title,
                'deadline': task.deadline.isoformat() if task.deadline else None,
                'priority': task.priority.value if task.priority else 'medium',
                'status': task.status.value
            })
    
    # Sort by deadline (None deadlines at end)
    due_tasks.sort(key=lambda x: (x['deadline'] is None, x['deadline'] or ''))
    
    # 3. Tasks user updated today (has progress_description and updated today)
    my_updates_today = []
    for assignment in user_assignments:
        task = assignment.task
        if (task.updated_at and task.updated_at >= today_start and 
            task.progress_description and task.status != TaskStatus.cancelled):
            my_updates_today.append({
                'task_id': task.id,
                'title': task.title,
                'progress_description': task.progress_description,
                'progress_percentage': task.progress_percentage,
                'updated_at': task.updated_at.isoformat()
            })
    
    return {
        'user': {
            'id': user.id,
            'name': user.name,
            'phone': user.phone
        },
        'completed_today': completed_today,
        'due_tasks': due_tasks,
        'my_updates_today': my_updates_today
    }


@router.get("/daily-assigned-report/{user_id}")
def get_daily_assigned_report(user_id: int, db: Session = Depends(get_db)):
    """
    Get data for assigned tasks report (for managers/owners).
    Returns: tasks created/assigned by user, progress updates on those tasks.
    """
    from server.models import Task, TaskAssignee, User
    from server.enums import TaskStatus
    from datetime import datetime, timedelta
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Tasks created by this user (active ones)
    created_tasks = db.query(Task).filter(
        Task.created_by == user_id,
        Task.status.notin_([TaskStatus.cancelled])
    ).all()
    
    assigned_tasks = []
    updates_received = []
    
    for task in created_tasks:
        # Get active assignees
        active_assignees = [a for a in task.assignees if a.unassigned_at is None]
        assignee_names = [a.user.name for a in active_assignees if a.user]
        
        assigned_tasks.append({
            'id': task.id,
            'title': task.title,
            'deadline': task.deadline.isoformat() if task.deadline else None,
            'status': task.status.value,
            'priority': task.priority.value if task.priority else 'medium',
            'progress_percentage': task.progress_percentage or 0,
            'assignee_names': assignee_names
        })
        
        # Check if task was updated today with progress
        if (task.updated_at and task.updated_at >= today_start and 
            task.progress_description):
            updates_received.append({
                'task_id': task.id,
                'title': task.title,
                'progress_description': task.progress_description,
                'progress_percentage': task.progress_percentage,
                'assignee_names': assignee_names,
                'updated_at': task.updated_at.isoformat()
            })
    
    # Sort by deadline
    assigned_tasks.sort(key=lambda x: (x['deadline'] is None, x['deadline'] or ''))
    
    return {
        'user': {
            'id': user.id,
            'name': user.name,
            'phone': user.phone
        },
        'assigned_tasks': assigned_tasks,
        'updates_received': updates_received
    }


@router.get("/users-for-daily-reports")
def get_users_for_daily_reports(db: Session = Depends(get_db)):
    """
    Get all users with their roles for daily report distribution.
    """
    from server.models import User, UserRole
    from server.enums import Role
    
    users = db.query(User).all()
    
    result = []
    for user in users:
        # Get user's role
        user_role = db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.org_id == user.org_id
        ).first()
        
        role_value = user_role.role.value if user_role else Role.intern.value
        
        result.append({
            'id': user.id,
            'name': user.name,
            'phone': user.phone,
            'role': role_value,
            'can_assign': role_value in ['owner', 'manager']
        })
    
    return result
