"""Pydantic schemas and request validation for SentinelLab API."""

import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator

VALID_STATES = {"created", "ready", "running", "succeeded", "failed", "deleted"}
SANDBOX_NAME_PATTERN = re.compile(r"^sbx-[a-z0-9]{8,}$")


class RunBase(BaseModel):
    run_id: str
    sandbox_name: str
    problem_id: str
    state: str
    execution_target: str

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("run_id cannot be empty")
        return v.strip()

    @field_validator("sandbox_name")
    @classmethod
    def validate_sandbox_name(cls, v: str) -> str:
        if not v or not SANDBOX_NAME_PATTERN.match(v):
            raise ValueError(
                "sandbox_name must start with 'sbx-' followed by at least 8 lowercase alphanumeric characters (e.g. sbx-12345678)"
            )
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if v not in VALID_STATES:
            raise ValueError(
                f"state must be one of {sorted(list(VALID_STATES))}"
            )
        return v

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, v: str) -> str:
        if v != "celesto_sandbox":
            raise ValueError(
                "execution_target must equal 'celesto_sandbox'"
            )
        return v


class RunCreate(RunBase):
    pass


class RunResponse(RunBase):
    model_config = ConfigDict(from_attributes=True)
    created_at: str | None = None
    updated_at: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
