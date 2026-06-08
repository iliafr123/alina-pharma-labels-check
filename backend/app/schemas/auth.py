import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.users import UserRole


class LoginRequest(BaseModel):
    email: str  # login may be an email or a plain username (e.g. "admin")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.specialist


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: str | None = None  # allow plain usernames, not only emails
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None
