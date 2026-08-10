from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.middleware.auth_middleware import get_current_user
from app.schemas.profile import (
    ProfileResponse,
    ProfileUpdate,
)

router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
)


@router.get(
    "/{email}",
    response_model=ProfileResponse,
)
def get_profile(
    email: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    if email != current_user.email:
        raise HTTPException(status_code=403, detail="Cannot view another user's profile")

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return user


@router.put(
    "/{email}",
    response_model=ProfileResponse,
)
def update_profile(
    email: str,
    profile: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    if email != current_user.email:
        raise HTTPException(status_code=403, detail="Cannot update another user's profile")

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user.full_name = profile.full_name
    user.age = profile.age
    user.gender = profile.gender
    user.occupation = profile.occupation

    db.commit()
    db.refresh(user)

    return user
