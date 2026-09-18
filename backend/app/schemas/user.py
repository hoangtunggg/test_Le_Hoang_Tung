import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr

PASSWORD_MIN_CHARACTERS = 6
PASSWORD_MAX_BYTES = 72


def validate_password(password: str) -> str:
    if len(password) < PASSWORD_MIN_CHARACTERS:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_CHARACTERS} characters"
        )
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} UTF-8 bytes")
    return password


Password = Annotated[str, AfterValidator(validate_password)]


class UserCreate(BaseModel):
    email: EmailStr
    password: Password


class UserLogin(BaseModel):
    email: EmailStr
    password: Password


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str
