from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from server.schemas import UserCreate, UserLogin, Token
from server.models import User, AuthCredential, Organisation, UserRole, Role, TokenBlacklist
from server.dependencies import get_db, get_current_user, security
from server.security import hash_password, verify_password, create_access_token
import jwt
from datetime import datetime

router = APIRouter()

# =========================================================
# AUTH ENDPOINTS
# =========================================================
@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
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
    
    user = User(
        org_id=org.id,
        name=user_data.name,
        phone=user_data.phone,
        department=user_data.department
    )
    db.add(user)
    db.flush()
    
    auth = AuthCredential(
        user_id=user.id,
        password_hash=hash_password(user_data.password)
    )
    db.add(auth)
    
    role = Role.owner if is_org_creator else Role.intern
    user_role = UserRole(
        user_id=user.id,
        org_id=org.id,
        role=role
    )
    db.add(user_role)
    db.commit()
    
    token = create_access_token({"sub": user.id, "org_id": org.id})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == credentials.phone).first()
    if not user or not user.auth_credential:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(credentials.password, user.auth_credential.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user.id, "org_id": user.org_id})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/logout")
def logout(
    credentials = Depends(security),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")
        expires_at = datetime.utcfromtimestamp(exp) if exp else datetime.utcnow()
    except Exception:
        expires_at = datetime.utcnow()

    blacklisted = TokenBlacklist(token=token, expires_at=expires_at)
    db.add(blacklisted)
    db.commit()
    
    return {"message": "Logged out successfully"}
