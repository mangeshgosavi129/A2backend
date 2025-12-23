from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from server.schemas import UserCreate, UserLogin, Token
from server.models import User, AuthCredential, Organisation, UserRole
from server.dependencies import get_db, get_current_user
from server.security import hash_password, verify_password, create_access_token

router = APIRouter()

# =========================================================
# AUTH ENDPOINTS
# =========================================================
@router.post("/auth/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
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

@router.post("/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == credentials.phone).first()
    if not user or not user.auth_credential:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(credentials.password, user.auth_credential.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Include org_id in token
    token = create_access_token({"sub": user.id, "org_id": user.org_id})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/auth/logout")
def logout(current_user: User = Depends(get_current_user)):
    # In a production app, you'd invalidate the token here
    return {"message": "Logged out successfully"}
