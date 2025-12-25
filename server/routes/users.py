from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from server.schemas import UserResponse, UserUpdate
from server.models import User
from server.dependencies import get_db, get_current_user, get_current_user_with_role

router = APIRouter()

# =========================================================
# USER ENDPOINTS
# =========================================================
@router.get("/", response_model=List[UserResponse])
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

@router.get("/{user_id}", response_model=UserResponse)
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

@router.put("/{user_id}", response_model=UserResponse)
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

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
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
