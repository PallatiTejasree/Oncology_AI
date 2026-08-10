from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# -----------------------------
# Register
# -----------------------------
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


# -----------------------------
# Login
# -----------------------------
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# -----------------------------
# Forgot Password
# -----------------------------
class ForgotPassword(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=6)


class ChangePassword(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


# -----------------------------
# Complete Profile
# -----------------------------
class CompleteProfile(BaseModel):
    email: EmailStr
    full_name: str
    age: int
    gender: str
    occupation: Optional[str] = None


# -----------------------------
# Login Response
# -----------------------------
class LoginResponse(BaseModel):
    id: int
    email: EmailStr
    profile_completed: bool

    class Config:
        from_attributes = True


# -----------------------------
# User Response
# -----------------------------
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    profile_completed: bool

    class Config:
        from_attributes = True


# -----------------------------
# Generic Success Message
# -----------------------------
class MessageResponse(BaseModel):
    message: str
