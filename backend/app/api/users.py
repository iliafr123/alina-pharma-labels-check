import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import require_admin, get_current_user
from app.core.security import get_password_hash
from app.models.users import User
from app.models.audit_log import AuditLog
from app.schemas.auth import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    user = User(email=data.email, password_hash=get_password_hash(data.password), role=data.role)
    db.add(user)
    db.add(AuditLog(
        user_id=current_user.id, action="create_user", resource_type="user",
        ip_address=request.client.host if request.client else None,
    ))
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/me/password")
async def change_my_password(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new = (payload or {}).get("password") or ""
    if len(new) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не короче 6 символов")
    current_user.password_hash = get_password_hash(new)
    db.add(current_user)
    db.add(AuditLog(user_id=current_user.id, action="change_own_password", resource_type="user", resource_id=str(current_user.id)))
    await db.commit()
    return {"message": "Пароль изменён"}


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if data.email:
        user.email = data.email
    if data.role:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.password_hash = get_password_hash(data.password)
    db.add(AuditLog(
        user_id=current_user.id, action="update_user", resource_type="user", resource_id=str(user_id),
        ip_address=request.client.host if request.client else None,
    ))
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя деактивировать самого себя")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.is_active = False
    db.add(AuditLog(
        user_id=current_user.id, action="deactivate_user", resource_type="user", resource_id=str(user_id),
        ip_address=request.client.host if request.client else None,
    ))
    await db.commit()
