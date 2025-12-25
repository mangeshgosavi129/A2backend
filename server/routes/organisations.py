from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from server.schemas import OrganisationResponse, RoleAssignment
from server.models import Organisation, UserRole
from server.dependencies import get_db, get_current_user, get_current_user_with_role
from server.permissions import can_assign_roles, check_org_access
from typing import List
from server.models import User

router = APIRouter()

# =========================================================
# ORGANISATION ENDPOINTS
# =========================================================
@router.get("/{org_id}", response_model=OrganisationResponse)
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

@router.get("/", response_model=List[OrganisationResponse])
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
@router.post("/{org_id}/roles", status_code=status.HTTP_200_OK)
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

@router.get("/{org_id}/roles")
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

