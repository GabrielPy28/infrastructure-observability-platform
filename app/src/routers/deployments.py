import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import build_where, get_db, paginate
from ..schemas import Deployment, DeploymentStatus, Environment, Page, SortOrder

router = APIRouter(prefix="/api/v1/deployments", tags=["deployments"])

SORT_COLUMNS = {
    "id": "id",
    "started_at": "started_at",
    "duration_seconds": "duration_seconds",
}
SortColumn = Literal["id", "started_at", "duration_seconds"]


@router.get("", response_model=Page[Deployment])
def list_deployments(
    service: str | None = None,
    environment: Environment | None = None,
    status: DeploymentStatus | None = None,
    sort: SortColumn = "started_at",
    order: SortOrder = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    where, params = build_where(
        {
            "service = ?": service,
            "environment = ?": environment,
            "status = ?": status,
        }
    )
    return paginate(
        db,
        f"SELECT * FROM deployments {where}",
        f"SELECT COUNT(*) FROM deployments {where}",
        params,
        SORT_COLUMNS[sort],
        order,
        page,
        page_size,
    )


@router.get("/{deployment_id}", response_model=Deployment)
def get_deployment(deployment_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM deployments WHERE id = ?", [deployment_id]).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return dict(row)
