"""Genera la base de datos SQLite con datos ficticios de infraestructura.

El resultado es determinista: la misma semilla produce exactamente los mismos
datos, lo que permite tests con valores exactos e imágenes reproducibles.

Uso:
    python -m seed.generate --output data/infra.db
"""

import argparse
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DEFAULT_SEED = 42
# Fecha fija de referencia: usar "ahora" rompería el determinismo.
REFERENCE_DATE = datetime(2026, 9, 1, tzinfo=timezone.utc)

COUNTS = {
    "servers": 500,
    "incidents": 5000,
    "deployments": 2000,
}

DATACENTERS = [
    ("use1-a", "Virginia A", "us-east-1", "aws"),
    ("use1-b", "Virginia B", "us-east-1", "aws"),
    ("usw2-a", "Oregon A", "us-west-2", "aws"),
    ("euw1-a", "Dublin A", "eu-west-1", "aws"),
    ("euc1-a", "Frankfurt A", "eu-central-1", "aws"),
    ("sae1-a", "Sao Paulo A", "sa-east-1", "aws"),
    ("ape1-a", "Singapore A", "ap-southeast-1", "aws"),
    ("mad-01", "Madrid On-Prem", "eu-south-2", "on-premise"),
    ("bog-01", "Bogota On-Prem", "sa-north-1", "on-premise"),
    ("mex-01", "Queretaro On-Prem", "mx-central-1", "on-premise"),
]

ENVIRONMENTS = [("production", 0.5), ("staging", 0.25), ("development", 0.25)]
ROLES = ["web", "api", "db", "cache", "queue", "worker", "lb"]
OPERATING_SYSTEMS = ["Ubuntu 24.04", "Ubuntu 22.04", "Debian 12", "RHEL 9", "Amazon Linux 2023"]
CPU_CORES = [2, 4, 8, 16, 32]
MEMORY_GB = [4, 8, 16, 32, 64, 128]

INCIDENT_TYPES = {
    "high_cpu": "CPU usage exceeded {value}%",
    "high_memory": "Memory usage exceeded {value}%",
    "disk_full": "Disk usage exceeded {value}%",
    "service_down": "Health check failed {value} consecutive times",
    "network_latency": "Network latency above {value} ms",
    "certificate_expiring": "TLS certificate expires in {value} days",
}
SEVERITIES = [("low", 0.35), ("medium", 0.35), ("high", 0.2), ("critical", 0.1)]

SERVICES = ["auth-service", "billing-api", "inventory-api", "notification-worker", "web-frontend", "search-api"]
DEPLOYMENT_STATUSES = [("succeeded", 0.85), ("failed", 0.1), ("rolled_back", 0.05)]


def weighted(rng: random.Random, options: list[tuple[str, float]]) -> str:
    values, weights = zip(*options, strict=True)
    return rng.choices(values, weights=weights, k=1)[0]


def server_status(cpu: float, memory: float, disk: float) -> str:
    """El estado se deriva del uso de recursos, igual que haría un monitor real."""
    peak = max(cpu, memory, disk)
    if peak >= 90:
        return "critical"
    if peak >= 75:
        return "warning"
    return "healthy"


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


SATURATION_PROBABILITY = 0.2


def resource_usage(rng: random.Random) -> list[float]:
    """Uso de CPU, memoria y disco.

    La mayoría de servidores tienen un uso sano; una fracción tiene un recurso
    saturado (75-99.9 %), lo que produce una mezcla realista de warning/critical.
    """
    values = [rng.betavariate(2, 3.5) * 100 for _ in range(3)]
    if rng.random() < SATURATION_PROBABILITY:
        values[rng.randrange(3)] = rng.uniform(75, 99.9)
    return [round(min(99.9, value), 1) for value in values]


def generate_datacenters() -> list[tuple]:
    return [(index, *row) for index, row in enumerate(DATACENTERS, start=1)]


def generate_servers(rng: random.Random, fake: Faker) -> list[tuple]:
    rows = []
    for server_id in range(1, COUNTS["servers"] + 1):
        datacenter_id = rng.randint(1, len(DATACENTERS))
        code = DATACENTERS[datacenter_id - 1][0]
        environment = weighted(rng, ENVIRONMENTS)
        role = rng.choice(ROLES)
        cpu, memory, disk = resource_usage(rng)
        created_at = REFERENCE_DATE - timedelta(days=rng.randint(30, 900))
        rows.append(
            (
                server_id,
                f"{role}-{environment[:4]}-{code}-{server_id:04d}",
                datacenter_id,
                environment,
                rng.choice(OPERATING_SYSTEMS),
                fake.unique.ipv4_private(),
                rng.choice(CPU_CORES),
                rng.choice(MEMORY_GB),
                cpu,
                memory,
                disk,
                server_status(cpu, memory, disk),
                iso(created_at),
            )
        )
    return rows


def generate_incidents(rng: random.Random) -> list[tuple]:
    rows = []
    for incident_id in range(1, COUNTS["incidents"] + 1):
        incident_type = rng.choice(list(INCIDENT_TYPES))
        value = {
            "service_down": rng.randint(3, 10),
            "network_latency": rng.randint(200, 2000),
            "certificate_expiring": rng.randint(1, 14),
        }.get(incident_type, rng.randint(90, 99))
        created_at = REFERENCE_DATE - timedelta(minutes=rng.randint(0, 180 * 24 * 60))
        status = weighted(rng, [("resolved", 0.75), ("acknowledged", 0.1), ("open", 0.15)])
        resolved_at = created_at + timedelta(minutes=rng.randint(5, 72 * 60)) if status == "resolved" else None
        rows.append(
            (
                incident_id,
                rng.randint(1, COUNTS["servers"]),
                weighted(rng, SEVERITIES),
                incident_type,
                INCIDENT_TYPES[incident_type].format(value=value),
                status,
                iso(created_at),
                iso(resolved_at) if resolved_at else None,
            )
        )
    return rows


def generate_deployments(rng: random.Random, fake: Faker) -> list[tuple]:
    rows = []
    for deployment_id in range(1, COUNTS["deployments"] + 1):
        started_at = REFERENCE_DATE - timedelta(minutes=rng.randint(0, 365 * 24 * 60))
        rows.append(
            (
                deployment_id,
                rng.choice(SERVICES),
                f"v{rng.randint(1, 4)}.{rng.randint(0, 20)}.{rng.randint(0, 9)}",
                fake.sha1()[:7],
                weighted(rng, ENVIRONMENTS),
                weighted(rng, DEPLOYMENT_STATUSES),
                fake.user_name(),
                iso(started_at),
                rng.randint(30, 900),
            )
        )
    return rows


def build_database(output: Path, seed: int = DEFAULT_SEED) -> Path:
    """Crea (o recrea) la base de datos en `output` y devuelve su ruta."""
    rng = random.Random(seed)
    fake = Faker()
    fake.seed_instance(seed)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)

    connection = sqlite3.connect(output)
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.executemany("INSERT INTO datacenters VALUES (?, ?, ?, ?, ?)", generate_datacenters())
        connection.executemany(
            "INSERT INTO servers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            generate_servers(rng, fake),
        )
        connection.executemany("INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?, ?)", generate_incidents(rng))
        connection.executemany(
            "INSERT INTO deployments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            generate_deployments(rng, fake),
        )
        connection.commit()
    finally:
        connection.close()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=Path("data/infra.db"))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    path = build_database(args.output, args.seed)
    print(f"Base de datos generada en {path}")


if __name__ == "__main__":
    main()
