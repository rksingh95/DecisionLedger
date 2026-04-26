"""
DAI Policy Models
=================

Pydantic models for PolicyVersion and related structures.
"""

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class PolicyStatus(StrEnum):
    draft = "draft"
    active = "active"
    deprecated = "deprecated"
    superseded = "superseded"


class PolicyChangeType(StrEnum):
    new_version = "new_version"
    amendment = "amendment"
    emergency_amendment = "emergency_amendment"
    deprecation = "deprecation"
    supersession = "supersession"


class PolicyClause(BaseModel):
    clause_id: str = Field(description="Identifier like '3.1'")
    title: str
    content_hash: str = Field(description="SHA-256 of clause text")
    effective_from: datetime
    mandatory: bool


class PolicyVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str
    version: str
    status: PolicyStatus
    title: str
    description: str
    effective_from: datetime
    effective_to: datetime | None = None
    supersedes_version: str | None = None
    change_type: PolicyChangeType
    change_summary: str = Field(max_length=500)
    clauses: list[PolicyClause]
    authorized_decision_types: list[str]
    max_auto_approve_confidence: float = Field(ge=0.0, le=1.0)
    exception_types_allowed: list[str]
    retention_period_days: int
    policy_hash: str = Field(description="SHA-256 of entire policy content")
    created_at: datetime
    created_by: str
    workspace_id: str

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        if not SEMVER_RE.match(v):
            raise ValueError(f"version must match semver X.Y.Z, got: {v!r}")
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be strictly after effective_from")
        return self


class PolicyDiff(BaseModel):
    policy_id: str
    from_version: str
    to_version: str
    diffed_at: datetime
    clauses_added: list[str]
    clauses_removed: list[str]
    clauses_modified: list[str]
    threshold_changed: bool
    max_auto_approve_confidence_delta: float | None = None
    exception_types_added: list[str]
    exception_types_removed: list[str]
    risk_level_change: Literal["increased", "decreased", "unchanged"]
    summary: str


class PolicyVersionCreate(BaseModel):
    policy_id: str
    version: str
    status: PolicyStatus
    title: str
    description: str
    effective_from: datetime
    effective_to: datetime | None = None
    supersedes_version: str | None = None
    change_type: PolicyChangeType
    change_summary: str = Field(max_length=500)
    clauses: list[PolicyClause]
    authorized_decision_types: list[str]
    max_auto_approve_confidence: float = Field(ge=0.0, le=1.0)
    exception_types_allowed: list[str]
    retention_period_days: int
    created_by: str
    workspace_id: str

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        if not SEMVER_RE.match(v):
            raise ValueError(f"version must match semver X.Y.Z, got: {v!r}")
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be strictly after effective_from")
        return self


class PolicyResolveRequest(BaseModel):
    policy_id: str
    at_timestamp: datetime
    workspace_id: str
