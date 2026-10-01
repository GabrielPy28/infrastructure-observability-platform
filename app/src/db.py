"""Único punto de acceso a la base de datos.

La base se abre en modo solo lectura e inmutable: cada réplica sirve una copia
idéntica empaquetada en la imagen, por lo que los pods no tienen estado.
Migrar a PostgreSQL/RDS implicaría cambiar solo este módulo.
"""

import sqlite3
from collections.abc import Iterator
from typing import Any

from .config import get_settings

SORT_ORDERS = {"asc": "ASC", "desc": "DESC"}


def connect() -> sqlite3.Connection:
    db_path = get_settings().db_path.resolve()
    # check_same_thread=False: FastAPI ejecuta dependencias y endpoints síncronos
    # en un pool de hilos, así que la conexión puede abrirse en un hilo y usarse
    # en otro. Es seguro: cada conexión la usa una sola petición a la vez y la
    # base es de solo lectura.
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro&immutable=1", uri=True, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def get_db() -> Iterator[sqlite3.Connection]:
    """Dependencia de FastAPI: una conexión por petición."""
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def is_ready() -> bool:
    try:
        connection = connect()
        try:
            connection.execute("SELECT 1 FROM servers LIMIT 1").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return False
    return True


def build_where(conditions: dict[str, Any]) -> tuple[str, list[Any]]:
    """Construye un WHERE parametrizado con las condiciones que tengan valor.

    Las claves son condiciones SQL escritas en el código (p. ej. "s.status = ?"),
    nunca por el usuario; los valores siempre viajan como parámetros para
    evitar SQL injection.
    """
    active = {clause: value for clause, value in conditions.items() if value is not None}
    where = f"WHERE {' AND '.join(active)}" if active else ""
    return where, list(active.values())


def paginate(
    db: sqlite3.Connection,
    base_query: str,
    count_query: str,
    params: list[Any],
    order_by: str,
    order: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Ejecuta una consulta paginada. `order_by` debe venir de una lista blanca."""
    total = db.execute(count_query, params).fetchone()[0]
    rows = db.execute(
        f"{base_query} ORDER BY {order_by} {SORT_ORDERS[order]} LIMIT ? OFFSET ?",
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }
