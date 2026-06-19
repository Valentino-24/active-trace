"""Pydantic schemas for Usuario (extended User with PII) entity."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Request schema for creating a new user with PII."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    email_hash: str | None = None  # computed server-side if omitted
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(max_length=255)
    nombre: str = Field(max_length=255)
    apellidos: str = Field(max_length=255)
    dni: Optional[str] = Field(default=None, max_length=100)
    cuil: Optional[str] = Field(default=None, max_length=100)
    cbu: Optional[str] = Field(default=None, max_length=255)
    alias_cbu: Optional[str] = Field(default=None, max_length=255)
    banco: Optional[str] = Field(default=None, max_length=255)
    regional: Optional[str] = Field(default=None, max_length=255)
    legajo: Optional[str] = Field(default=None, max_length=100)
    legajo_profesional: Optional[str] = Field(default=None, max_length=100)
    facturador: bool = False
    estado: str = "activo"
    is_active: bool = True


class UserUpdate(BaseModel):
    """Request schema for updating an existing user."""

    model_config = ConfigDict(extra="forbid")

    email: Optional[EmailStr] = None
    display_name: Optional[str] = Field(default=None, max_length=255)
    nombre: Optional[str] = Field(default=None, max_length=255)
    apellidos: Optional[str] = Field(default=None, max_length=255)
    dni: Optional[str] = Field(default=None, max_length=100)
    cuil: Optional[str] = Field(default=None, max_length=100)
    cbu: Optional[str] = Field(default=None, max_length=255)
    alias_cbu: Optional[str] = Field(default=None, max_length=255)
    banco: Optional[str] = Field(default=None, max_length=255)
    regional: Optional[str] = Field(default=None, max_length=255)
    legajo: Optional[str] = Field(default=None, max_length=100)
    legajo_profesional: Optional[str] = Field(default=None, max_length=100)
    facturador: Optional[bool] = None
    estado: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserResponse(BaseModel):
    """Response schema for a single user with full PII (detail view).

    PII fields are returned decrypted — the endpoint requiring this
    schema should be protected by `usuarios:*` permissions.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    nombre: str | None = None
    apellidos: str | None = None
    dni: str | None = None
    cuil: str | None = None
    cbu: str | None = None
    alias_cbu: str | None = None
    banco: str | None = None
    regional: str | None = None
    legajo: str | None = None
    legajo_profesional: str | None = None
    facturador: bool = False
    estado: str = "activo"
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class UserListResponseItem(BaseModel):
    """Response schema for a user in a list (no full PII)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email_masked: str
    display_name: str
    nombre: str | None = None
    apellidos: str | None = None
    legajo: str | None = None
    facturador: bool = False
    estado: str = "activo"
    is_active: bool = True


class UserListResponse(BaseModel):
    """Response schema for paginated list of users."""

    model_config = ConfigDict(extra="forbid")

    items: list[UserListResponseItem]
    total: int
