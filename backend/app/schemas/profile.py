from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ProfileResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    profile_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    full_name: str
    age: int
    gender: str
    occupation: Optional[str] = None