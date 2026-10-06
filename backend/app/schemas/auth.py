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
    monthly_income: float | None = None
    monthly_savings_target: float | None = None
    budgeting_style: str = "balanced"

    model_config = {"from_attributes": True}


class OnboardingIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    monthly_income: float | None = Field(default=None, ge=0)
    income_frequency: str = Field(default="monthly", max_length=20)
    monthly_savings_target: float | None = Field(default=None, ge=0)
    budgeting_style: str = Field(default="balanced", max_length=30)
    initial_account_name: str | None = Field(default=None, max_length=120)
    initial_account_kind: str | None = Field(default="bank", max_length=20)
    initial_account_balance: float | None = Field(default=0)


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
