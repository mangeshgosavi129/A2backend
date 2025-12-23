from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, validator
from server.models import TaskStatus, TaskPriority, MessageDirection, MessageChannel

# =========================================================
# PYDANTIC SCHEMAS
# =========================================================

# Organisation Schemas
class OrganisationCreate(BaseModel):
    name: str

class OrganisationResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# User Schemas
class UserCreate(BaseModel):
    name: str
    phone: str
    password: str
    department: Optional[str] = None
    org_name: Optional[str] = None  # For creating new org
    org_id: Optional[int] = None    # For joining existing org

class UserLogin(BaseModel):
    phone: str
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None

class RoleResponse(BaseModel):
    role: Role
    org_id: int
    
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    org_id: int
    name: str
    phone: str
    department: Optional[str]
    created_at: datetime
    role: Optional[Role] = None
    
    class Config:
        from_attributes = True

class RoleAssignment(BaseModel):
    user_id: int
    role: Role

class ClientCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    project_name: Optional[str] = None

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    project_name: Optional[str] = None

class ClientResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    project_name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    client_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: Optional[TaskStatus] = TaskStatus.assigned
    priority: Optional[TaskPriority] = TaskPriority.medium
    deadline: Optional[datetime] = None
    checklist: Optional[List[dict]] = []
    progress_percentage: Optional[int] = 0

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    deadline: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    progress_description: Optional[str] = None
    progress_percentage: Optional[int] = None

class TaskCancel(BaseModel):
    cancellation_reason: str

class TaskAssign(BaseModel):
    user_id: int

class TaskAssignMultiple(BaseModel):
    user_ids: List[int]

class TaskUnassign(BaseModel):
    user_id: int

class ChecklistItem(BaseModel):
    text: str
    completed: bool = False

class ChecklistUpdate(BaseModel):
    index: int
    text: Optional[str] = None
    completed: Optional[bool] = None

class ChecklistRemove(BaseModel):
    index: int

class TaskAssigneeResponse(BaseModel):
    user_id: int
    user_name: str
    assigned_at: datetime

    class Config:
        from_attributes = True

class TaskResponse(BaseModel):
    id: int
    client_id: Optional[int]
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    deadline: Optional[datetime]
    end_datetime: Optional[datetime]
    checklist: Optional[List[dict]]
    progress_description: Optional[str]
    progress_percentage: Optional[int]
    created_by: Optional[int]
    cancellation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    assignees: List[TaskAssigneeResponse] = []
    
    @validator('assignees', pre=True, always=True)
    def filter_active_assignees(cls, v):
        if not v:
            return []
        # Filter out those with unassigned_at (only keep active assignments)
        # v is a list of TaskAssignee ORM objects when coming from_attributes
        return [a for a in v if getattr(a, 'unassigned_at', None) is None]

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    user_id: Optional[int] = None
    task_id: Optional[int] = None
    direction: MessageDirection
    channel: MessageChannel
    message_text: Optional[str] = None
    payload: Optional[dict] = None

class MessageResponse(BaseModel):
    id: int
    user_id: Optional[int]
    task_id: Optional[int]
    direction: MessageDirection
    channel: MessageChannel
    message_text: Optional[str]
    payload: Optional[dict]
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
