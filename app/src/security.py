"""Autenticación por API key (header X-API-Key)."""

import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import get_settings

# auto_error=False: la validación la decide require_api_key, no FastAPI.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: str | None = Security(api_key_header)) -> None:
    expected = get_settings().api_key
    if expected is None:
        return
    # compare_digest evita ataques de temporización al comparar secretos.
    if provided is None or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
