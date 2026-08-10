from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserRegister,
    UserLogin,
    ForgotPassword,
    CompleteProfile,
    ChangePassword,
)

from app.core.security import (
    hash_password,
    verify_password,
)
from app.auth.jwt_handler import create_access_token
from app.middleware.auth_middleware import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/me")
def current_account(current_user: User = Depends(get_current_user)):
    """Validate the saved JWT and return the authenticated account state."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "profile_completed": current_user.profile_completed,
    }


# =====================================================
# REGISTER
# =====================================================

@router.post("/register")
def register_user(
    user: UserRegister,
    db: Session = Depends(get_db),
):

    existing_user = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Email already registered.",
        )

    new_user = User(

        email=user.email,

        password_hash=hash_password(
            user.password
        ),

        profile_completed=False,

    )

    db.add(new_user)

    db.commit()

    db.refresh(new_user)

    access_token = create_access_token(
        {"sub": str(new_user.id), "email": new_user.email}
    )

    return {

        "message": "User registered successfully.",

        "id": new_user.id,

        "email": new_user.email,

        "profile_completed": new_user.profile_completed,

        "access_token": access_token,

        "token_type": "bearer",

    }


# =====================================================
# LOGIN
# =====================================================

@router.post("/login")
def login_user(
    user: UserLogin,
    db: Session = Depends(get_db),
):

    existing_user = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    account_created = False

    # First-time users can start from the same screen. Creating the account
    # here removes the need for an administrator or Swagger registration step.
    if existing_user is None:
        if len(user.password) < 6:
            raise HTTPException(
                status_code=422,
                detail="A new account password must contain at least 6 characters.",
            )
        existing_user = User(
            email=user.email,
            password_hash=hash_password(user.password),
            profile_completed=False,
        )
        db.add(existing_user)
        db.commit()
        db.refresh(existing_user)
        account_created = True

    if not account_created and not verify_password(
        user.password,
        existing_user.password_hash,
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    existing_user.last_login = datetime.utcnow()

    db.commit()

    access_token = create_access_token(
        {"sub": str(existing_user.id), "email": existing_user.email}
    )

    return {

        "id": existing_user.id,

        "email": existing_user.email,

        "profile_completed":
            existing_user.profile_completed,

        "access_token": access_token,

        "token_type": "bearer",

        "account_created": account_created,

    }
# =====================================================
# COMPLETE PROFILE
# =====================================================

@router.post("/profile")
def complete_profile(
    profile: CompleteProfile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    if profile.email != current_user.email:
        raise HTTPException(status_code=403, detail="Cannot update another user's profile.")

    user = current_user

    user.full_name = profile.full_name
    user.age = profile.age
    user.gender = profile.gender
    user.occupation = profile.occupation

    user.profile_completed = True

    db.commit()

    db.refresh(user)

    return {

        "message": "Profile completed successfully.",

        "profile_completed": True,

    }


# =====================================================
# FORGOT PASSWORD
# =====================================================

@router.post("/forgot-password")
def forgot_password(
    request: ForgotPassword,
    db: Session = Depends(get_db),
):

    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if user is None:

        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    user.password_hash = hash_password(
        request.new_password
    )

    db.commit()

    return {

        "message": "Password updated successfully."

    }


@router.post("/change-password")
def change_password(
    request: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(request.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if request.old_password == request.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current password.")
    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Password changed successfully. Please sign in again."}


# =====================================================
# GET USER PROFILE
# =====================================================

@router.get("/profile/{email}")
def get_profile(
    email: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    if email != current_user.email:
        raise HTTPException(status_code=403, detail="Cannot view another user's profile.")

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if user is None:

        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    return {

        "id": user.id,

        "email": user.email,

        "full_name": user.full_name,

        "age": user.age,

        "gender": user.gender,

        "occupation": user.occupation,

        "profile_completed": user.profile_completed,

        "created_at": user.created_at,

        "last_login": user.last_login,

    }
