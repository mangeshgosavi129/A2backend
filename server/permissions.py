from .enums import Role
def can_create_task(role: Role) -> bool:
    """Check if role can create tasks"""
    return role in [Role.owner, Role.manager, Role.employee]

def can_update_any_task(role: Role) -> bool:
    """Check if role can update any task in org"""
    return role in [Role.owner, Role.manager]

def can_update_assigned_task(user_id: int, task, role: Role) -> bool:
    """Check if user can update a task assigned to them"""
    # Owner and Manager can update any task
    if can_update_any_task(role):
        return True
    
    # Employee and Intern can only update tasks assigned to them
    for assignee in task.assignees:
        if assignee.user_id == user_id and assignee.unassigned_at is None:
            return True
    
    return False

def can_delete_task(role: Role) -> bool:
    """Check if role can delete/cancel tasks"""
    return role in [Role.owner, Role.manager]

def can_assign_task(role: Role) -> bool:
    """Check if role can assign tasks to others"""
    return role in [Role.owner, Role.manager]

def can_manage_clients(role: Role) -> bool:
    """Check if role can create/update/delete clients"""
    return role in [Role.owner, Role.manager]

def can_manage_users(role: Role) -> bool:
    """Check if role can create/update/delete users"""
    return role in [Role.owner, Role.manager]

def can_assign_roles(role: Role) -> bool:
    """Check if role can assign roles to users"""
    return role == Role.owner

def can_view_all_org_tasks(role: Role) -> bool:
    """Check if role can view all org tasks (vs only assigned ones)"""
    return role in [Role.owner, Role.manager]

def get_role_hierarchy_value(role: Role) -> int:
    """Get numeric value for role hierarchy (higher = more privileges)"""
    hierarchy = {
        Role.intern: 1,
        Role.employee: 2,
        Role.manager: 3,
        Role.owner: 4
    }
    return hierarchy.get(role, 0)

def can_modify_user_role(requester_role: Role, target_role: Role) -> bool:
    """Check if requester can modify a user with target_role"""
    # Only owners can change roles
    if requester_role != Role.owner:
        return False
    
    # Owners can modify anyone's role
    return True

def check_org_access(user_org_id: int, resource_org_id: int) -> bool:
    """Verify user has access to resource in same org"""
    return user_org_id == resource_org_id
