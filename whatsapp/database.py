# whatsapp/database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import enum
import os
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# DATABASE SETUP
# =========================================================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/taskbot")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =========================================================
# ENUMS (Duplicated)
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

# =========================================================
# DATABASE MODELS (Duplicated)
# =========================================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    department = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    auth_credential = relationship("AuthCredential", back_populates="user", uselist=False)
    tasks_created = relationship("Task", back_populates="creator")
    task_assignments = relationship("TaskAssignee", back_populates="user")
    messages = relationship("Message", back_populates="user")

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
    name = Column(String(150), nullable=False)
    phone = Column(String(20))
    project_name = Column(String(150))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    tasks = relationship("Task", back_populates="client")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
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
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    direction = Column(SQLEnum(MessageDirection), nullable=False)
    channel = Column(SQLEnum(MessageChannel), nullable=False)
    message_text = Column(Text)
    payload = Column(JSONB)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_state = Column(JSONB, default={})
    
    user = relationship("User", back_populates="messages")
    task = relationship("Task", back_populates="messages")
