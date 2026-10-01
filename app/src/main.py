"""Infrastructure Monitoring API."""

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from . import db
from .config import get_settings
from .routers import datacenters, deployments, incidents, servers
from .schemas import Health
from .security import require_api_key

settings = get_settings()
description = """
**Infrastructure Monitoring API** provides a read-only RESTful interface for
monitoring simulated infrastructure environments. 🚀

The API exposes realistic, deterministic infrastructure data generated with Faker:
datacenters, servers, incidents, and deployments.

## Infrastructure

You can:

* **Read datacenters** and how many servers each one hosts.
* **Read servers** with their CPU, memory, and disk usage, and filter them by
  environment, region, status, datacenter, or hostname.
* **Get a server health summary** (healthy / warning / critical), using the same filters.

## Monitoring

You can:

* **Read incidents** and filter them by severity, type, status, and server.
* **Read deployments** and filter the deployment history by service, environment, and status.

All list endpoints support **pagination** and **sorting**.

## Health

* `/healthz` — **liveness**: the process is running.
* `/readyz` — **readiness**: the database is available and the pod can receive traffic.

## DevOps

This API is designed as a containerized application and serves as the
backend for a DevOps infrastructure project using:

* **FastAPI** for the REST API.
* **Docker** for containerization.
* **Kubernetes** for orchestration and scaling.
* **Terraform** for infrastructure as code.
* **GitHub Actions** for CI/CD.
"""

app = FastAPI(
    title="Infrastructure Monitoring API",
    description=description,
    summary="Simulated infrastructure monitoring API for DevOps environments.",
    version=settings.app_version,
    contact={
        "name": "Gabriel Piñero",
        "url": "https://www.linkedin.com/in/gabriel-piñero-a151321a9/",
    },
)

# Los endpoints de datos requieren API key para proteger el acceso
# a la información de infraestructura. /healthz y /readyz quedan
# abiertos porque son endpoints operacionales destinados a determinar
# si el proceso está vivo y si puede recibir tráfico, y deben poder
# ser consultados directamente por Kubernetes sin autenticación.
for router in (datacenters.router, servers.router, incidents.router, deployments.router):
    app.include_router(router, dependencies=[Depends(require_api_key)])


@app.get("/healthz", response_model=Health, tags=["health"])
def liveness():
    """Liveness: el proceso responde. No consulta dependencias a propósito,
    para que un fallo externo no provoque reinicios en cascada."""
    return Health(status="healthy", version=settings.app_version, environment=settings.environment)


@app.get("/readyz", response_model=Health, tags=["health"], responses={503: {"model": Health}})
def readiness():
    """Readiness: el pod puede recibir tráfico solo si la base de datos responde."""
    if get_settings().simulate_readiness_failure or not db.is_ready():
        return JSONResponse(
            status_code=503,
            content=Health(
                status="unavailable", version=settings.app_version, environment=settings.environment
            ).model_dump(),
        )
    return Health(status="ready", version=settings.app_version, environment=settings.environment)
