"""Configuración leída de variables de entorno (inyectadas por ConfigMap/Secret en Kubernetes)."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    app_version: str
    environment: str


def get_settings() -> Settings:
    return Settings(
        db_path=Path(os.getenv("DB_PATH", "data/infra.db")),
        app_version=os.getenv("APP_VERSION", "dev"),
        environment=os.getenv("APP_ENV", "local"),
    )
