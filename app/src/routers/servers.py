import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import build_where, get_db, paginate
from ..schemas import Environment, Page, Server, ServerStatus, ServerSummary, SortOrder

router = APIRouter(prefix="/api/v1/servers", tags=["servers"])

FROM = "FROM servers s JOIN datacenters d ON d.id = s.datacenter_id"
SELECT = f"SELECT s.*, d.code AS datacenter_code, d.region {FROM}"

# Lista blanca: el usuario elige una clave, nunca escribe SQL.
SORT_COLUMNS = {
    "id": "s.id",
    "hostname": "s.hostname",
    "cpu_usage": "s.cpu_usage",
    "memory_usage": "s.memory_usage",
    "disk_usage": "s.disk_usage",
    "created_at": "s.created_at",
}
SortColumn = Literal["id", "hostname", "cpu_usage", "memory_usage", "disk_usage", "created_at"]


def server_conditions(
    environment: Environment | None = None,
    region: str | None = None,
    status: ServerStatus | None = None,
    datacenter_id: int | None = None,
    search: str | None = Query(None, min_length=2, description="Búsqueda parcial por hostname"),
) -> dict:
    return {
        "s.environment = ?": environment,
        "d.region = ?": region,
        "s.status = ?": status,
        "s.datacenter_id = ?": datacenter_id,
        "s.hostname LIKE ?": f"%{search}%" if search else None,
    }


@router.get("", response_model=Page[Server])
def list_servers(
    conditions: dict = Depends(server_conditions),
    sort: SortColumn = "id",
    order: SortOrder = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    where, params = build_where(conditions)
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


@router.get("/summary", response_model=ServerSummary)
def servers_summary(conditions: dict = Depends(server_conditions), db: sqlite3.Connection = Depends(get_db)):
    """Agregación por estado; acepta los mismos filtros que el listado."""
    where, params = build_where(conditions)
    row = db.execute(
        f"""
        SELECT COUNT(*)                                          AS total,
               COALESCE(SUM(s.status = 'healthy'), 0)            AS healthy,
               COALESCE(SUM(s.status = 'warning'), 0)            AS warning,
               COALESCE(SUM(s.status = 'critical'), 0)           AS critical
        {FROM} {where}
        """,
        params,
    ).fetchone()
    return dict(row)


@router.get("/{server_id}", response_model=Server)
def get_server(server_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(f"{SELECT} WHERE s.id = ?", [server_id]).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return dict(row)
