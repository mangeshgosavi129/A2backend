import enum
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
