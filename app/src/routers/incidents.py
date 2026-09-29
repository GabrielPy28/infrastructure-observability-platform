import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import build_where, get_db, paginate
from ..schemas import Incident, IncidentStatus, Page, Severity, SortOrder

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

FROM = "FROM incidents i JOIN servers s ON s.id = i.server_id"
SELECT = f"SELECT i.*, s.hostname {FROM}"

SORT_COLUMNS = {
    "id": "i.id",
    "created_at": "i.created_at",
    "resolved_at": "i.resolved_at",
}
SortColumn = Literal["id", "created_at", "resolved_at"]


@router.get("", response_model=Page[Incident])
def list_incidents(
    severity: Severity | None = None,
    status: IncidentStatus | None = None,
    type: str | None = None,
    server_id: int | None = None,
    sort: SortColumn = "created_at",
    order: SortOrder = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    where, params = build_where(
        {
            "i.severity = ?": severity,
            "i.status = ?": status,
            "i.type = ?": type,
            "i.server_id = ?": server_id,
        }
    )
    return paginate(
        db,
        f"{SELECT} {where}",
        f"SELECT COUNT(*) {FROM} {where}",
        params,
        SORT_COLUMNS[sort],
        order,
        page,
        page_size,
    )


@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(f"{SELECT} WHERE i.id = ?", [incident_id]).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return dict(row)
