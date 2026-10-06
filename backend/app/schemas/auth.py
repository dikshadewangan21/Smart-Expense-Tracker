from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    currency: str
    timezone: str
    onboarded: bool
    is_demo: bool

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v):
        return " ".join(v.split()) if v is not None else None

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, v):
        if v is None:
            return None
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError("Unknown timezone. Use a name like Asia/Kolkata.")
        return v
