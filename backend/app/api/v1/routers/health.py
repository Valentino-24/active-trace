"""Health-check endpoint: liveness + database readiness."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Report application liveness and database readiness.

    Returns 200 with JSON body:
        {"status": "ok", "database": "up|down"}

    The database check runs a lightweight SELECT 1.
    If the check fails, the endpoint still responds 200
    but reports database: "down" (degraded, not crashed).
    """
    db_status = "up"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — broad catch to avoid crash on DB down
        db_status = "down"

    return {"status": "ok", "database": db_status}
