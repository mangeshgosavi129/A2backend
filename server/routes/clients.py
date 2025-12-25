from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from server.schemas import ClientResponse, ClientCreate, ClientUpdate
from server.models import Client, User
from server.dependencies import get_db, get_current_user, get_current_user_with_role

router = APIRouter()

# =========================================================
# CLIENT ENDPOINTS
# =========================================================
@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
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

@router.get("/", response_model=List[ClientResponse])
def get_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    clients = db.query(Client).filter(Client.org_id == current_user.org_id).all()
    return clients

@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    client = db.query(Client).filter(Client.id == client_id, Client.org_id == current_user.org_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.put("/{client_id}", response_model=ClientResponse)
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

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
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
