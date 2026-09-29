import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..schemas import Datacenter

router = APIRouter(prefix="/api/v1/datacenters", tags=["datacenters"])

QUERY = """
    SELECT d.*, COUNT(s.id) AS server_count
    FROM datacenters d
    LEFT JOIN servers s ON s.datacenter_id = d.id
"""


@router.get("", response_model=list[Datacenter])
def list_datacenters(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(f"{QUERY} GROUP BY d.id ORDER BY d.id").fetchall()
    return [dict(row) for row in rows]


@router.get("/{datacenter_id}", response_model=Datacenter)
def get_datacenter(datacenter_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(f"{QUERY} WHERE d.id = ? GROUP BY d.id", [datacenter_id]).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Datacenter not found")
    return dict(row)
