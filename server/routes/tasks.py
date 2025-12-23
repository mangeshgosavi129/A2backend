from typing import List, Optional
from datetime import datetime, timedelta
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from server.schemas import (
    TaskCreate, TaskResponse, TaskUpdate, TaskCancel, 
    TaskAssign, TaskAssignMultiple, TaskUnassign, 
    TaskAssigneeResponse, ChecklistItem, ChecklistUpdate, ChecklistRemove
)
from server.models import Task, User, TaskAssignee, TaskStatus
from server.dependencies import get_db, get_current_user

router = APIRouter()

# =========================================================
# TASK ENDPOINTS
# =========================================================
@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task_data: TaskCreate,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_create_task
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_create_task(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Employee+ role required")
    
    # Deduplication check: Prevent duplicate tasks within 30 seconds
    cutoff_time = datetime.utcnow() - timedelta(seconds=30)
    existing_task = db.query(Task).filter(
        Task.org_id == current_user.org_id,
        Task.title == task_data.title,
        Task.description == task_data.description,
        Task.created_by == current_user.id,
        Task.deadline == task_data.deadline,
        Task.priority == task_data.priority,
        Task.status == task_data.status,
        Task.created_at >= cutoff_time
    ).first()

    if existing_task:
        logging.info(f"Deduplicated task creation for user {current_user.id}: {task_data.title}")
        return existing_task

    # Auto-set org_id from current user
    task = Task(**task_data.dict(), org_id=current_user.org_id, created_by=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@router.get("/tasks", response_model=List[TaskResponse])
def get_tasks(
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_view_all_org_tasks
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Base filter: org_id and exclude cancelled
    query = db.query(Task).filter(
        Task.org_id == current_user.org_id,
        Task.status != TaskStatus.cancelled
    )
    
    # Role-based filtering: Employee/Intern see only assigned tasks
    if not can_view_all_org_tasks(current_role):
        # Filter to only tasks assigned to current user
        query = query.join(TaskAssignee).filter(
            TaskAssignee.user_id == current_user.id,
            TaskAssignee.unassigned_at == None
        )
    
    tasks = query.all()
    return tasks

@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.org_id == current_user.org_id  # Tenant isolation
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # Treat cancelled tasks as soft deleted
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_update_assigned_task
    
    current_user = context["user"]
    current_role = context["role"]
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.org_id == current_user.org_id  # Tenant isolation
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prevent updates to cancelled tasks (soft delete)
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=403, detail="Cannot update cancelled task")
    
    # Check permission: Manager+ OR assigned user
    if not can_update_assigned_task(current_user.id, task, current_role):
        raise HTTPException(status_code=403, detail="Permission denied: not authorized to update this task")
    
    # Deduplication check: If the update requests no changes to the current state, return early
    # This prevents redundant notifications and DB writes
    changes_detected = False
    update_data = task_data.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        current_value = getattr(task, key)
        # Handle enum comparisons and other types robustly
        if current_value != value:
            changes_detected = True
            break
    
    if not changes_detected and update_data:
        logging.info(f"Deduplicated task update for task {task_id}: No changes detected")
        return task

    for key, value in update_data.items():
        setattr(task, key, value)
    
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    
    # Send WhatsApp notification to all assigned users
    active_assignees = db.query(TaskAssignee).filter(
        TaskAssignee.task_id == task_id,
        TaskAssignee.unassigned_at.is_(None)
    ).all()
    
    if active_assignees:
        try:
            from whatsapp_worker.send import send_task_update_notification
            task_dict = {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status.value if task.status else "N/A",
                "priority": task.priority.value if task.priority else "medium",
                "deadline": task.deadline.strftime("%Y-%m-%d %H:%M") if task.deadline else None
            }
            
            for assignee in active_assignees:
                user = assignee.user
                if user and user.phone:
                    result, status_code = send_task_update_notification(user.phone, task_dict)
                    if status_code == 200:
                        logging.info(f"✅ WhatsApp update notification sent to {user.name} ({user.phone}) for task {task.id}")
                    else:
                        logging.error(f"❌ WhatsApp update notification failed for {user.name}: {result}")
        except Exception as e:
            logging.error(f"Failed to send task update notification: {e}")
    
    return task

@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(
    task_id: int,
    cancel_data: TaskCancel,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_delete_task
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_delete_task(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Manager+ role required")
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.org_id == current_user.org_id  # Tenant isolation
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Deduplication check: If already cancelled, return success immediately
    if task.status == TaskStatus.cancelled:
        logging.info(f"Deduplicated task cancellation for task {task_id}: Already cancelled")
        return task
    
    # Get active assignees before cancelling
    active_assignees = db.query(TaskAssignee).filter(
        TaskAssignee.task_id == task_id,
        TaskAssignee.unassigned_at.is_(None)
    ).all()
    
    task.status = TaskStatus.cancelled
    task.cancellation_reason = cancel_data.cancellation_reason
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    
    # Send WhatsApp notification to all assigned users
    if active_assignees:
        try:
            from whatsapp_worker.send import send_task_cancellation_notification
            task_dict = {
                "id": task.id,
                "title": task.title,
                "cancellation_reason": task.cancellation_reason
            }
            
            for assignee in active_assignees:
                user = assignee.user
                if user and user.phone:
                    result, status_code = send_task_cancellation_notification(user.phone, task_dict)
                    if status_code == 200:
                        logging.info(f"✅ WhatsApp cancellation notification sent to {user.name} ({user.phone}) for task {task.id}")
                    else:
                        logging.error(f"❌ WhatsApp cancellation notification failed for {user.name}: {result}")
        except Exception as e:
            logging.error(f"Failed to send task cancellation notification: {e}")
    
    return task

# =========================================================
# TASK ASSIGNMENT ENDPOINTS
# =========================================================
@router.post("/tasks/{task_id}/assign")
def assign_task(
    task_id: int,
    assign_data: TaskAssign,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_assign_task
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_assign_task(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Manager+ role required")
    task = db.query(Task).filter(Task.id == task_id, Task.org_id == current_user.org_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prevent operations on cancelled tasks
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=403, detail="Cannot modify cancelled task")
    
    # Ensure assigned user is in the same org
    user = db.query(User).filter(User.id == assign_data.user_id, User.org_id == current_user.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already assigned
    existing = db.query(TaskAssignee).filter(
        TaskAssignee.task_id == task_id,
        TaskAssignee.user_id == assign_data.user_id,
        TaskAssignee.unassigned_at.is_(None)
    ).first()
    
    if existing:
        # Idempotent: Already assigned, just return success without error
        logging.info(f"User {assign_data.user_id} already assigned to task {task_id}, skipping duplicate")
        return {"message": "Task assigned successfully", "note": "User was already assigned"}
    
    assignment = TaskAssignee(task_id=task_id, user_id=assign_data.user_id)
    db.add(assignment)
    db.commit()
    
    # Send WhatsApp notification
    try:
        from whatsapp_worker.send import send_task_notification
        task_dict = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "priority": task.priority.value if task.priority else "medium",
            "deadline": task.deadline.strftime("%Y-%m-%d %H:%M") if task.deadline else None
        }
        result, status_code = send_task_notification(user.phone, task_dict)
        if status_code == 200:
            logging.info(f"✅ WhatsApp notification sent to {user.name} ({user.phone}) for task {task.id}")
        else:
            logging.error(f"❌ WhatsApp notification failed for {user.name}: {result}")
    except Exception as e:
        logging.error(f"Failed to send task notification: {e}")
    
    return {"message": "Task assigned successfully"}

@router.post("/tasks/{task_id}/assign-multiple")
def assign_task_multiple(
    task_id: int,
    assign_data: TaskAssignMultiple,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_assign_task
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_assign_task(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Manager+ role required")
    task = db.query(Task).filter(Task.id == task_id, Task.org_id == current_user.org_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prevent operations on cancelled tasks
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=403, detail="Cannot modify cancelled task")
    
    for user_id in assign_data.user_ids:
        # Check if user exists and belongs to the same org
        user = db.query(User).filter(User.id == user_id, User.org_id == current_user.org_id).first()
        if not user:
            continue
        
        # Check if already assigned
        existing = db.query(TaskAssignee).filter(
            TaskAssignee.task_id == task_id,
            TaskAssignee.user_id == user_id,
            TaskAssignee.unassigned_at.is_(None)
        ).first()
        
        if not existing:
            assignment = TaskAssignee(task_id=task_id, user_id=user_id)
            db.add(assignment)
            
            # Send WhatsApp notification
            try:
                from whatsapp_worker.send import send_task_notification
                task_dict = {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority.value if task.priority else "medium",
                    "deadline": task.deadline.strftime("%Y-%m-%d %H:%M") if task.deadline else None
                }
                send_task_notification(user.phone, task_dict)
            except Exception as e:
                logging.error(f"Failed to send task notification to user {user_id}: {e}")
    
    db.commit()
    return {"message": "Task assigned to multiple users successfully"}

@router.post("/tasks/{task_id}/unassign")
def unassign_task(
    task_id: int,
    unassign_data: TaskUnassign,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_assign_task
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_assign_task(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Manager+ role required")
    # Check if task exists and is not cancelled
    task = db.query(Task).filter(Task.id == task_id, Task.org_id == current_user.org_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=403, detail="Cannot modify cancelled task")
    
    assignment = db.query(TaskAssignee).filter(
        TaskAssignee.task_id == task_id,
        TaskAssignee.user_id == unassign_data.user_id,
        TaskAssignee.unassigned_at.is_(None)
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    assignment.unassigned_at = datetime.utcnow()
    db.commit()
    return {"message": "User unassigned successfully"}

@router.get("/tasks/{task_id}/assignments", response_model=List[TaskAssigneeResponse])
def get_task_assignments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.org_id == current_user.org_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prevent operations on cancelled tasks
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Filter for active assignments (where unassigned_at is None)
    active_assignees = [a for a in task.assignees if a.unassigned_at is None]
    return active_assignees

# =========================================================
# CHECKLIST ENDPOINTS
# =========================================================
@router.post("/tasks/{task_id}/checklist/add", response_model=TaskResponse)
def add_checklist_item(
    task_id: int,
    item: ChecklistItem,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_update_assigned_task
    
    current_user = context["user"]
    current_role = context["role"]
    task = db.query(Task).filter(Task.id == task_id, Task.org_id == current_user.org_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prevent operations on cancelled tasks
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=403, detail="Cannot modify cancelled task")
        
    # Check permission
    if not can_update_assigned_task(current_user.id, task, current_role):
        raise HTTPException(status_code=403, detail="Permission denied: not authorized to update this task")
    
    checklist = task.checklist or []
    checklist.append(item.dict())
    task.checklist = checklist
    flag_modified(task, "checklist")  # Explicitly mark as modified
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task

@router.put("/tasks/{task_id}/checklist/update", response_model=TaskResponse)
def update_checklist_item(
    task_id: int,
    update_data: ChecklistUpdate,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_update_assigned_task
    
    current_user = context["user"]
    current_role = context["role"]
    task = db.query(Task).filter(Task.id == task_id, Task.org_id == current_user.org_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prevent operations on cancelled tasks
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=403, detail="Cannot modify cancelled task")
    
    # Check permission
    if not can_update_assigned_task(current_user.id, task, current_role):
        raise HTTPException(status_code=403, detail="Permission denied: not authorized to update this task")
    
    checklist = task.checklist or []
    if update_data.index >= len(checklist):
        raise HTTPException(status_code=400, detail="Invalid checklist index")
    
    if update_data.text is not None:
        checklist[update_data.index]["text"] = update_data.text
    if update_data.completed is not None:
        checklist[update_data.index]["completed"] = update_data.completed
    
    task.checklist = checklist
    flag_modified(task, "checklist")  # Explicitly mark as modified
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task

@router.delete("/tasks/{task_id}/checklist/remove", response_model=TaskResponse)
def remove_checklist_item(
    task_id: int,
    remove_data: ChecklistRemove,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_update_assigned_task
    
    current_user = context["user"]
    current_role = context["role"]
    task = db.query(Task).filter(Task.id == task_id, Task.org_id == current_user.org_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prevent operations on cancelled tasks
    if task.status == TaskStatus.cancelled:
        raise HTTPException(status_code=403, detail="Cannot modify cancelled task")
        
    # Check permission
    if not can_update_assigned_task(current_user.id, task, current_role):
        raise HTTPException(status_code=403, detail="Permission denied: not authorized to update this task")
    
    checklist = task.checklist or []
    if remove_data.index >= len(checklist):
        raise HTTPException(status_code=400, detail="Invalid checklist index")
    
    checklist.pop(remove_data.index)
    task.checklist = checklist
    flag_modified(task, "checklist")  # Explicitly mark as modified
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task
