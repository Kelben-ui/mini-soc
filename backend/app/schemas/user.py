from pydantic import BaseModel, Field


# Password policy mirrors backend/create_user.py so CLI- and dashboard-created
# users follow the same rule.
MIN_PASSWORD_LENGTH = 12


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=12, max_length=200)
    role: str = "analyst"


class UserUpdate(BaseModel):
    role: str


class PasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=200)
