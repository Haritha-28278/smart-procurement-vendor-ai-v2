"""
Authentication Routes & Middleware
JWT-based authentication using python-jose, passwords hashed with bcrypt.
Role-based access control: Admin, Procurement Manager, Vendor.
Direct SQL queries via get_db_cursor.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import bcrypt
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from backend.db.connection import get_db_cursor

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-procurement-jwt-key-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

security = HTTPBearer(auto_error=False)


# --- Pydantic Schemas ---
class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    role: str  # Admin, Procurement Manager, Vendor


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# --- Crypto & Token Helpers ---
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)


# --- Dependencies ---
def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with get_db_cursor() as cur:
        cur.execute("SELECT id, email, full_name, role, created_at FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")
        return user


def require_role(allowed_roles: List[str]):
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {allowed_roles}, your role is {current_user.get('role')}",
            )
        return current_user
    return role_checker


# --- Auth Endpoints ---
@router.post("/register", response_model=TokenResponse)
def register(user_data: UserRegister):
    valid_roles = ["Admin", "Procurement Manager", "Vendor"]
    if user_data.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of {valid_roles}",
        )

    with get_db_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (user_data.email,))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

        hashed = hash_password(user_data.password)
        cur.execute(
            """
            INSERT INTO users (email, password_hash, full_name, role)
            VALUES (%s, %s, %s, %s)
            """,
            (user_data.email, hashed, user_data.full_name, user_data.role),
        )

        cur.execute("SELECT id, email, full_name, role, created_at FROM users WHERE email = %s", (user_data.email,))
        created_user = cur.fetchone()

    token = create_access_token({"sub": created_user["email"], "role": created_user["role"], "id": created_user["id"]})
    return {"access_token": token, "token_type": "bearer", "user": created_user}


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin):
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, email, password_hash, full_name, role, created_at FROM users WHERE email = %s",
            (login_data.email,),
        )
        user = cur.fetchone()

    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user_info = {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "created_at": str(user["created_at"]) if user.get("created_at") else None,
    }
    token = create_access_token({"sub": user["email"], "role": user["role"], "id": user["id"]})
    return {"access_token": token, "token_type": "bearer", "user": user_info}


@router.get("/me")
def get_my_profile(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "role": current_user["role"],
        "created_at": str(current_user["created_at"]) if current_user.get("created_at") else None,
    }
