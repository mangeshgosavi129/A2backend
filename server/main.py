# main.py
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
import enum
import os
from dotenv import load_dotenv
import logging
# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# =========================================================
# DATABASE SETUP
# =========================================================
engine = create_engine(os.getenv("DATABASE_URL"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =========================================================
# ENUMS
# =========================================================
class TaskStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    on_hold = "on_hold"
    completed = "completed"
    cancelled = "cancelled"
    overdue = "overdue"

class TaskPriority(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"

class MessageDirection(str, enum.Enum):
    in_dir = "in"
    out = "out"
    system = "system"

class MessageChannel(str, enum.Enum):
    whatsapp = "whatsapp"
    web = "web"
    system = "system"

class Role(str, enum.Enum):
    owner = "owner"
    manager = "manager"
    employee = "employee"
    intern = "intern"

# =========================================================
# DATABASE MODELS
# =========================================================
class Organisation(Base):
    __tablename__ = "organisations"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    users = relationship("User", back_populates="organisation")
    clients = relationship("Client", back_populates="organisation")
    tasks = relationship("Task", back_populates="organisation")
    messages = relationship("Message", back_populates="organisation")
    user_roles = relationship("UserRole", back_populates="organisation")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    department = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organisation = relationship("Organisation", back_populates="users")
    auth_credential = relationship("AuthCredential", back_populates="user", uselist=False)
    tasks_created = relationship("Task", back_populates="creator")
    task_assignments = relationship("TaskAssignee", back_populates="user")
    messages = relationship("Message", back_populates="user")
    roles = relationship("UserRole", back_populates="user")

class UserRole(Base):
    __tablename__ = "user_roles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    org_id = Column(Integer, ForeignKey("organisations.id"), nullable=False)
    role = Column(SQLEnum(Role), nullable=False, default=Role.intern)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="roles")
    organisation = relationship("Organisation", back_populates="user_roles")

class AuthCredential(Base):
    __tablename__ = "auth_credentials"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="auth_credential")

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"), nullable=False)
    name = Column(String(150), nullable=False)
    phone = Column(String(20))
    project_name = Column(String(150))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organisation = relationship("Organisation", back_populates="clients")
    tasks = relationship("Task", back_populates="client")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"))
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.assigned)
    priority = Column(SQLEnum(TaskPriority), nullable=False, default=TaskPriority.medium)
    deadline = Column(DateTime)
    end_datetime = Column(DateTime)
    checklist = Column(JSONB, default=[])
    progress_description = Column(Text)
    progress_percentage = Column(Integer, CheckConstraint('progress_percentage >= 0 AND progress_percentage <= 100'))
    created_by = Column(Integer, ForeignKey("users.id"))
    cancellation_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organisation = relationship("Organisation", back_populates="tasks")
    client = relationship("Client", back_populates="tasks")
    creator = relationship("User", back_populates="tasks_created")
    assignees = relationship("TaskAssignee", back_populates="task")
    messages = relationship("Message", back_populates="task")

class TaskAssignee(Base):
    __tablename__ = "task_assignees"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    unassigned_at = Column(DateTime)
    
    task = relationship("Task", back_populates="assignees")
    user = relationship("User", back_populates="task_assignments")

    @property
    def user_name(self):
        return self.user.name if self.user else "Unknown"

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    direction = Column(SQLEnum(MessageDirection), nullable=False)
    channel = Column(SQLEnum(MessageChannel), nullable=False)
    message_text = Column(Text)
    payload = Column(JSONB)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_state = Column(JSONB, default={})
    
    organisation = relationship("Organisation", back_populates="messages")
    user = relationship("User", back_populates="messages")
    task = relationship("Task", back_populates="messages")

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

# =========================================================
# SECURITY
# =========================================================
from server.security_utils import (
    create_access_token, 
    hash_password, 
    verify_password,
    SECRET_KEY,
    ALGORITHM
)

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    # Basic sanity checks
    if not SECRET_KEY:
        # Fatal server misconfiguration
        print("ERROR: SECRET_KEY is not set")
        raise HTTPException(status_code=500, detail="Server misconfiguration: SECRET_KEY not set")

    try:
        # credentials.credentials should already be the token string, but some clients
        # may accidentally send the entire header value including 'Bearer'.
        token = credentials.credentials
        if token.startswith("Bearer "):
            token = token.split(" ", 1)[1]
            print("DEBUG: stripped 'Bearer ' prefix, token now:", token)

        # decode the JWT
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_signature": True, "verify_exp": True, "verify_sub": False}
        )
        # print("DEBUG: JWT payload:", payload)

        sub = payload.get("sub")
        if sub is None:
            print("DEBUG: 'sub' missing in token payload")
            raise HTTPException(status_code=401, detail="Invalid token: subject missing")

        # allow both numeric strings and integers
        try:
            user_id = int(sub)
        except (TypeError, ValueError):
            # not an integer-like sub; provide a clear error for debugging
            print(f"DEBUG: token 'sub' is not an integer: {sub!r}")
            raise HTTPException(status_code=401, detail="Invalid token: subject is not an integer id")

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        print("DEBUG: token decode error:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print("DEBUG: unexpected error while validating token:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid token")

    # finally, look up user in DB
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        print(f"DEBUG: no user found with id={user_id}")
        raise HTTPException(status_code=401, detail="User not found")
    
    # Validate org_id from token matches user's org
    token_org_id = payload.get("org_id")
    if token_org_id and user.org_id != token_org_id:
        print(f"DEBUG: org_id mismatch - token: {token_org_id}, user: {user.org_id}")
        raise HTTPException(status_code=401, detail="Invalid token: organisation mismatch")
    
    return user

# Helper to get user with their role
async def get_current_user_with_role(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user along with their role in the organisation"""
    from server.permissions import get_user_role_in_org
    
    role = get_user_role_in_org(db, current_user.id, current_user.org_id)
    return {"user": current_user, "role": role, "org_id": current_user.org_id}



# =========================================================
# PROMETHEUS
# =========================================================
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["endpoint"]
)

EXCEPTION_COUNT = Counter(
    "http_exceptions_total",
    "Total exceptions",
    ["endpoint"]
)

# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(title="Task Management API")

origins = [
    "https://gsstask.vercel.app",  # <--- This is the crucial line
    "http://localhost:8001",
    "http://localhost:5050",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],      # IMPORTANT – allows OPTIONS
    allow_headers=["*"],
)
# =========================================================
# AUTO-CREATE TABLES ON STARTUP
# =========================================================
@app.on_event("startup")
def init_database():
    print("🔄 Creating database tables if not exist...")
    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    if not existing_tables:
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created")
    else:
        print("ℹ️ Tables already exist:", existing_tables)

# =========================================================
# PROMETHEUS ENDPOINTS
# =========================================================

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(data, media_type=CONTENT_TYPE_LATEST)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()

    try:
        response = await call_next(request)
    except Exception:
        EXCEPTION_COUNT.labels(endpoint=request.url.path).inc()
        raise

    process_time = time.time() - start_time

    REQUEST_LATENCY.labels(endpoint=request.url.path).observe(process_time)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        http_status=response.status_code
    ).inc()

    return response

# =========================================================
# AUTH ENDPOINTS
# =========================================================
@app.post("/auth/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing = db.query(User).filter(User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")
    
    # Determine organisation
    org = None
    is_org_creator = False
    
    if user_data.org_name:
        # First user creating a new organisation
        existing_org = db.query(Organisation).filter(Organisation.name == user_data.org_name).first()
        if existing_org:
            raise HTTPException(status_code=400, detail="Organisation name already exists")
        
        org = Organisation(name=user_data.org_name)
        db.add(org)
        db.flush()
        is_org_creator = True
        
    elif user_data.org_id:
        # Joining existing organisation
        org = db.query(Organisation).filter(Organisation.id == user_data.org_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")
    else:
        raise HTTPException(
            status_code=400, 
            detail="Must provide either org_name (to create) or org_id (to join)"
        )
    
    # Create user
    user = User(
        org_id=org.id,
        name=user_data.name,
        phone=user_data.phone,
        department=user_data.department
    )
    db.add(user)
    db.flush()
    
    # Create auth credential
    auth = AuthCredential(
        user_id=user.id,
        password_hash=hash_password(user_data.password)
    )
    db.add(auth)
    
    # Assign role - Owner for org creator, Intern for others
    role = Role.owner if is_org_creator else Role.intern
    user_role = UserRole(
        user_id=user.id,
        org_id=org.id,
        role=role
    )
    db.add(user_role)
    db.commit()
    
    # Generate token with org_id
    token = create_access_token({"sub": user.id, "org_id": org.id})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == credentials.phone).first()
    if not user or not user.auth_credential:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(credentials.password, user.auth_credential.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Include org_id in token
    token = create_access_token({"sub": user.id, "org_id": user.org_id})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/logout")
def logout(current_user: User = Depends(get_current_user)):
    # In a production app, you'd invalidate the token here
    return {"message": "Logged out successfully"}

# =========================================================
# USER ENDPOINTS
# =========================================================
@app.get("/users", response_model=List[UserResponse])
def get_users(
    name: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Filter by org_id for tenant isolation
    query = db.query(User).filter(User.org_id == current_user.org_id)
    if name:
        query = query.filter(User.name.ilike(f"%{name}%"))
    if department:
        query = query.filter(User.department.ilike(f"%{department}%"))
    
    users = query.all()
    # Populate roles
    for user in users:
        # Find role for this user and org
        user_role = next((r for r in user.roles if r.org_id == current_user.org_id), None)
        user.role = user_role.role if user_role else Role.intern # Default to intern
        
    return users

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Filter by org_id for tenant isolation
    user = db.query(User).filter(User.id == user_id, User.org_id == current_user.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Populate role
    user_role = next((r for r in user.roles if r.org_id == current_user.org_id), None)
    user.role = user_role.role if user_role else Role.intern
    
    return user

@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_manage_users
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission: User can update themselves, or Manager+ can update anyone
    if current_user.id != user_id and not can_manage_users(current_role):
         raise HTTPException(status_code=403, detail="Permission denied: Cannot update other users")
    # Filter by org_id for tenant isolation
    user = db.query(User).filter(User.id == user_id, User.org_id == current_user.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_data.name is not None:
        user.name = user_data.name
    if user_data.department is not None:
        user.department = user_data.department
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user

@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_manage_users
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_manage_users(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Manager+ role required")
    # Filter by org_id for tenant isolation
    user = db.query(User).filter(User.id == user_id, User.org_id == current_user.org_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return None

# =========================================================
# ORGANISATION ENDPOINTS
# =========================================================
@app.get("/organisations/{org_id}", response_model=OrganisationResponse)
def get_organisation(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify user belongs to this org
    if current_user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied: not a member of this organisation")
    
    org = db.query(Organisation).filter(Organisation.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    
    return org

@app.get("/organisations", response_model=List[OrganisationResponse])
def list_organisations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # For now, users can only see their own organisation
    org = db.query(Organisation).filter(Organisation.id == current_user.org_id).all()
    return org

# =========================================================
# ROLE MANAGEMENT ENDPOINTS
# =========================================================
@app.post("/organisations/{org_id}/roles", status_code=status.HTTP_200_OK)
def assign_role(
    org_id: int,
    role_assignment: RoleAssignment,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_assign_roles, check_org_access
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Verify user is in this org
    if not check_org_access(current_user.org_id, org_id):
        raise HTTPException(status_code=403, detail="Access denied: not a member of this organisation")
    
    # Check permission
    if not can_assign_roles(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: only Owners can assign roles")
    
    # Verify target user exists and is in the org
    target_user = db.query(User).filter(User.id == role_assignment.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target_user.org_id != org_id:
        raise HTTPException(status_code=400, detail="User is not a member of this organisation")
    
    # Update or create role assignment
    existing_role = db.query(UserRole).filter(
        UserRole.user_id == role_assignment.user_id,
        UserRole.org_id == org_id
    ).first()
    
    if existing_role:
        existing_role.role = role_assignment.role
    else:
        new_role = UserRole(
            user_id=role_assignment.user_id,
            org_id=org_id,
            role=role_assignment.role
        )
        db.add(new_role)
    
    db.commit()
    return {"message": f"Role updated to {role_assignment.role.value} for user {role_assignment.user_id}"}

@app.get("/organisations/{org_id}/roles")
def list_org_roles(
    org_id: int,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import check_org_access
    
    current_user = context["user"]
    
    # Verify user is in this org
    if not check_org_access(current_user.org_id, org_id):
        raise HTTPException(status_code=403, detail="Access denied: not a member of this organisation")
    
    # Get all user roles in this org
    user_roles = db.query(UserRole, User).join(User, UserRole.user_id == User.id).filter(
        UserRole.org_id == org_id
    ).all()
    
    result = []
    for user_role, user in user_roles:
        result.append({
            "user_id": user.id,
            "user_name": user.name,
            "role": user_role.role.value,
            "assigned_at": user_role.created_at
        })
    
    return result

# =========================================================
# CLIENT ENDPOINTS
# =========================================================
@app.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    client_data: ClientCreate,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_manage_clients
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_manage_clients(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Manager+ role required")
    
    # Auto-set org_id from current user
    client = Client(**client_data.dict(), org_id=current_user.org_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client

@app.get("/clients", response_model=List[ClientResponse])
def get_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Filter by org_id for tenant isolation
    clients = db.query(Client).filter(Client.org_id == current_user.org_id).all()
    return clients

@app.get("/clients/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    client = db.query(Client).filter(Client.id == client_id, Client.org_id == current_user.org_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@app.put("/clients/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    client_data: ClientUpdate,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_manage_clients
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_manage_clients(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Manager+ role required")
    
    client = db.query(Client).filter(Client.id == client_id, Client.org_id == current_user.org_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    for key, value in client_data.dict(exclude_unset=True).items():
        setattr(client, key, value)
    
    client.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(client)
    return client

@app.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    context = Depends(get_current_user_with_role),
    db: Session = Depends(get_db)
):
    from server.permissions import can_manage_clients
    
    current_user = context["user"]
    current_role = context["role"]
    
    # Check permission
    if not can_manage_clients(current_role):
        raise HTTPException(status_code=403, detail="Permission denied: Manager+ role required")
    
    client = db.query(Client).filter(Client.id == client_id, Client.org_id == current_user.org_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db.delete(client)
    db.commit()
    return None

# =========================================================
# TASK ENDPOINTS
# =========================================================
@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
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

@app.get("/tasks", response_model=List[TaskResponse])
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

@app.get("/tasks/{task_id}", response_model=TaskResponse)
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

@app.put("/tasks/{task_id}", response_model=TaskResponse)
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
            from whatsapp.client import send_task_update_notification
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

@app.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
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
            from whatsapp.client import send_task_cancellation_notification
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
@app.post("/tasks/{task_id}/assign")
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
        from whatsapp.client import send_task_notification
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

@app.post("/tasks/{task_id}/assign-multiple")
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
                from whatsapp.client import send_task_notification
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

@app.post("/tasks/{task_id}/unassign")
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

@app.get("/tasks/{task_id}/assignments", response_model=List[TaskAssigneeResponse])
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
@app.post("/tasks/{task_id}/checklist/add", response_model=TaskResponse)
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

@app.put("/tasks/{task_id}/checklist/update", response_model=TaskResponse)
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

@app.delete("/tasks/{task_id}/checklist/remove", response_model=TaskResponse)
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

# =========================================================
# MESSAGE ENDPOINTS
# =========================================================
@app.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
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

@app.get("/messages", response_model=List[MessageResponse])
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
