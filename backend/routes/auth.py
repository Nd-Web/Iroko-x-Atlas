"""
Auth routes — invite-only registration, login, password reset, profile management.
Public registration is disabled; access is granted by superadmin / admin invitation only.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.database import get_db, User, UserInvitation, PasswordResetToken, AuditLog
from models.schemas import (
    LoginRequest, AuthResponse, UserResponse,
    InviteRequest, AcceptInviteRequest, InviteTokenValidation,
    InvitationResponse, InvitationListResponse,
    ForgotPasswordRequest, ResetPasswordRequest,
    UpdateUserRequest,
)
from services.auth_utils import (
    hash_password, verify_password, create_access_token,
    generate_api_key, get_current_user, require_admin,
    generate_secure_token, INVITE_EXPIRE_HOURS, RESET_EXPIRE_HOURS,
)
from services.email import send_invite_email, send_password_reset_email

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    user.last_login = datetime.utcnow()
    db.add(AuditLog(user_id=user.id, action="user_login", resource="auth", details={"email": user.email}))
    db.commit()

    token = create_access_token(user.id, user.role)
    return AuthResponse(access_token=token, user=user)


# ─── Invite ───────────────────────────────────────────────────────────────────

@router.post("/invite", status_code=201)
async def invite_user(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Send an invitation email. Admin and superadmin only.
    Superadmin can invite any role; admin can only invite analyst/viewer."""
    if current_user.role == "admin" and payload.role in ("superadmin", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Admins can only invite analyst or viewer roles.",
        )

    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    existing_invite = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.email == payload.email,
            UserInvitation.used_at.is_(None),
            UserInvitation.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if existing_invite:
        raise HTTPException(
            status_code=409,
            detail="A pending invitation already exists for this email.",
        )

    token = generate_secure_token()
    invite = UserInvitation(
        email=payload.email,
        token=token,
        invited_by_id=current_user.id,
        role=payload.role,
        department=payload.department,
        personal_message=payload.personal_message,
        expires_at=datetime.utcnow() + timedelta(hours=INVITE_EXPIRE_HOURS),
    )
    db.add(invite)
    db.commit()

    sent = send_invite_email(
        to_email=payload.email,
        invited_by_name=current_user.full_name or current_user.email,
        invite_token=token,
        role=payload.role,
        department=payload.department,
        personal_message=payload.personal_message,
    )

    return {
        "message": f"Invitation sent to {payload.email}.",
        "email_delivered": sent,
        "invite_id": invite.id,
    }


@router.get("/invite/{token}", response_model=InviteTokenValidation)
async def validate_invite_token(token: str, db: Session = Depends(get_db)):
    """Validate an invitation token (called by the frontend before showing the sign-up form)."""
    invite = (
        db.query(UserInvitation)
        .filter(UserInvitation.token == token)
        .first()
    )
    if not invite:
        return InviteTokenValidation(valid=False)
    if invite.used_at:
        return InviteTokenValidation(valid=False)
    if invite.expires_at < datetime.utcnow():
        return InviteTokenValidation(valid=False)

    return InviteTokenValidation(
        valid=True,
        email=invite.email,
        role=invite.role,
        department=invite.department,
        invited_by=invite.invited_by.full_name or invite.invited_by.email,
        expires_at=invite.expires_at,
    )


@router.post("/accept-invite", response_model=AuthResponse)
async def accept_invite(payload: AcceptInviteRequest, db: Session = Depends(get_db)):
    """Complete registration using an invitation token."""
    invite = (
        db.query(UserInvitation)
        .filter(UserInvitation.token == payload.token)
        .first()
    )
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid invitation token.")
    if invite.used_at:
        raise HTTPException(status_code=400, detail="This invitation has already been used.")
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This invitation has expired.")

    existing = db.query(User).filter(User.email == invite.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=invite.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        organisation="MTN Nigeria",
        department=invite.department,
        role=invite.role,
        is_active=True,
        api_key=generate_api_key(),
    )
    db.add(user)

    invite.used_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role)
    return AuthResponse(access_token=token, user=user)


@router.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all invitations (admin and superadmin)."""
    invitations = db.query(UserInvitation).order_by(UserInvitation.created_at.desc()).all()
    items = []
    for inv in invitations:
        items.append(InvitationResponse(
            id=inv.id,
            email=inv.email,
            role=inv.role,
            department=inv.department,
            invited_by=inv.invited_by.full_name or inv.invited_by.email if inv.invited_by else None,
            expires_at=inv.expires_at,
            used_at=inv.used_at,
            created_at=inv.created_at,
        ))
    return InvitationListResponse(invitations=items, total=len(items))


@router.delete("/invitations/{invite_id}", status_code=204)
async def revoke_invitation(
    invite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Revoke a pending invitation."""
    invite = db.query(UserInvitation).filter(UserInvitation.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if invite.used_at:
        raise HTTPException(status_code=400, detail="Invitation already used — cannot revoke.")
    db.delete(invite)
    db.commit()


# ─── Password reset ───────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Request a password reset link. Always returns 200 to avoid email enumeration."""
    user = db.query(User).filter(User.email == payload.email, User.is_active == True).first()
    if user:
        # Invalidate any existing unexpired tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).delete()

        token = generate_secure_token()
        reset = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=RESET_EXPIRE_HOURS),
        )
        db.add(reset)
        db.commit()

        send_password_reset_email(
            to_email=user.email,
            full_name=user.full_name or "",
            reset_token=token,
        )

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == payload.token)
        .first()
    )
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    if reset.used_at:
        raise HTTPException(status_code=400, detail="This reset link has already been used.")
    if reset.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link has expired.")

    user = db.query(User).filter(User.id == reset.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user.hashed_password = hash_password(payload.new_password)
    reset.used_at = datetime.utcnow()
    db.commit()

    return {"message": "Password reset successfully. You can now log in with your new password."}


# ─── Profile ──────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update own profile (name, department). Role changes require superadmin."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.department is not None:
        current_user.department = payload.department
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/generate-key")
async def generate_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rotate API key for the current user."""
    current_user.api_key = generate_api_key()
    db.commit()
    return {
        "api_key": current_user.api_key,
        "message": "New API key generated. Previous key is now invalid.",
        "warning": "Store this key securely — it will not be shown again.",
    }
