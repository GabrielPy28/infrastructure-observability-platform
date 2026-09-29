"""Modelos de respuesta (contrato público de la API)."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

Environment = Literal["development", "staging", "production"]
ServerStatus = Literal["healthy", "warning", "critical"]
Severity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["open", "acknowledged", "resolved"]
DeploymentStatus = Literal["succeeded", "failed", "rolled_back"]
SortOrder = Literal["asc", "desc"]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Health(BaseModel):
    status: str
    version: str
    environment: str


class Datacenter(BaseModel):
    id: int
    code: str
    name: str
    region: str
    provider: str
    server_count: int


class Server(BaseModel):
    id: int
    hostname: str
    datacenter_id: int
    datacenter_code: str
    region: str
    environment: Environment
    os: str
    ip_address: str
    cpu_cores: int
    memory_gb: int
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    status: ServerStatus
    created_at: str


class ServerSummary(BaseModel):
    total: int
    healthy: int
    warning: int
    critical: int


class Incident(BaseModel):
    id: int
    server_id: int
    hostname: str
    severity: Severity
    type: str
    message: str
    status: IncidentStatus
    created_at: str
    resolved_at: str | None


class Deployment(BaseModel):
    id: int
    service: str
    version: str
    commit_sha: str
    environment: Environment
    status: DeploymentStatus
    deployed_by: str
    started_at: str
    duration_seconds: int
