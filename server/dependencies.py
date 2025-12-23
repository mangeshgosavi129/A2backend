from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
from server.database import SessionLocal
from server.models import User, UserRole
from server.enums import Role
from server.config import config
from sqlalchemy import and_

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    # Basic sanity checks
    if not config.SECRET_KEY:
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
            config.SECRET_KEY,
            algorithms=[config.ALGORITHM],
            options={"verify_signature": True, "verify_exp": True, "verify_sub": False}
        )
        # print("DEBUG: JWT payload:", payload)

        sub = payload.get("sub")
        if sub is None:
            print("DEBUG: 'sub' missing in token payload")
            raise HTTPException(status_code=401, detail="Invalid token: subject missing")
        
        # Verify org_id match if present in token (optional security check)
        token_org_id = payload.get("org_id")

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
        
    # Verify org consistency if token had org_id
    if token_org_id and user.org_id != token_org_id:
        print(f"DEBUG: token org_id {token_org_id} != user org_id {user.org_id}")
        raise HTTPException(status_code=401, detail="Token organization mismatch")
        
    return user

def get_user_role_in_org(db: Session, user_id: int, org_id: int) -> Role:
    """Get user's role in specified organisation"""
    user_role = db.query(UserRole).filter(
        and_(
            UserRole.user_id == user_id,
            UserRole.org_id == org_id
        )
    ).first()
    
    if user_role:
        return user_role.role
    
    # Default to intern if no role explicitly assigned
    return Role.intern

def get_current_user_with_role(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dependency that returns a dict with 'user' and 'role'.
    This avoids re-fetching the role in every endpoint.
    """
    role = get_user_role_in_org(db, current_user.id, current_user.org_id)
    return {"user": current_user, "role": role}