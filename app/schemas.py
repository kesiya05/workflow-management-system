from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str
    password: str


class UserIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=6)
    role: Literal["Admin", "Manager", "Employee"]
    manager_id: int | None = None


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = ""
    assignee_id: int
    due: datetime | None = None


class StatusIn(BaseModel):
    status: Literal["todo", "in_progress", "done"]


class RequestIn(BaseModel):
    kind: Literal["leave", "expense", "purchase"]
    description: str = Field(min_length=1)
    amount: float = Field(default=0, ge=0)


class DecisionIn(BaseModel):
    approve: bool
    comment: str = ""
