"""
User management routes — list, update role, deactivate, reactivate, delete.
All endpoints require admin or superadmin. Destructive operations require superadmin.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.database import get_db, User
from models.schemas import UserResponse, UserListResponse, UpdateUserRequest
from services.auth_utils import get_current_user, require_admin, require_superadmin

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all users. Admin and superadmin only."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return UserListResponse(users=users, total=len(users))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Update a user's profile or role. Superadmin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Use /api/auth/me to update your own profile.")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.department is not None:
        user.department = payload.department
    if payload.role is not None:
        if payload.role == "superadmin":
            raise HTTPException(
                status_code=403,
                detail="Cannot promote to superadmin via API — update the database directly.",
            )
        user.role = payload.role

    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Deactivate a user account (blocks login, preserves data). Superadmin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is already deactivated.")

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Reactivate a previously deactivated user. Superadmin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.is_active:
        raise HTTPException(status_code=400, detail="User is already active.")

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Permanently delete a user and all their data. Superadmin only. Irreversible."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Cannot delete a superadmin account.")

    db.delete(user)
    db.commit()
