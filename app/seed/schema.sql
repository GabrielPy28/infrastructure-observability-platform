-- Esquema de la base de datos de monitoreo de infraestructura.
-- La base se genera en tiempo de build (etapa "seed" del Dockerfile) y se
-- sirve en modo solo lectura: los pods no guardan estado.

CREATE TABLE datacenters (
    id          INTEGER PRIMARY KEY,
    code        TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    region      TEXT    NOT NULL,
    provider    TEXT    NOT NULL
);

CREATE TABLE servers (
    id              INTEGER PRIMARY KEY,
    hostname        TEXT    NOT NULL UNIQUE,
    datacenter_id   INTEGER NOT NULL REFERENCES datacenters (id),
    environment     TEXT    NOT NULL CHECK (environment IN ('development', 'staging', 'production')),
    os              TEXT    NOT NULL,
    ip_address      TEXT    NOT NULL,
    cpu_cores       INTEGER NOT NULL,
    memory_gb       INTEGER NOT NULL,
    cpu_usage       REAL    NOT NULL,
    memory_usage    REAL    NOT NULL,
    disk_usage      REAL    NOT NULL,
    status          TEXT    NOT NULL CHECK (status IN ('healthy', 'warning', 'critical')),
    created_at      TEXT    NOT NULL
);

CREATE TABLE incidents (
    id          INTEGER PRIMARY KEY,
    server_id   INTEGER NOT NULL REFERENCES servers (id),
    severity    TEXT    NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    type        TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    status      TEXT    NOT NULL CHECK (status IN ('open', 'acknowledged', 'resolved')),
    created_at  TEXT    NOT NULL,
    resolved_at TEXT
);

CREATE TABLE deployments (
    id                  INTEGER PRIMARY KEY,
    service             TEXT    NOT NULL,
    version             TEXT    NOT NULL,
    commit_sha          TEXT    NOT NULL,
    environment         TEXT    NOT NULL CHECK (environment IN ('development', 'staging', 'production')),
    status              TEXT    NOT NULL CHECK (status IN ('succeeded', 'failed', 'rolled_back')),
    deployed_by         TEXT    NOT NULL,
    started_at          TEXT    NOT NULL,
    duration_seconds    INTEGER NOT NULL
);

-- Índices para los filtros más usados por la API.
CREATE INDEX idx_servers_datacenter   ON servers (datacenter_id);
CREATE INDEX idx_servers_environment  ON servers (environment);
CREATE INDEX idx_servers_status       ON servers (status);
CREATE INDEX idx_incidents_server     ON incidents (server_id);
CREATE INDEX idx_incidents_severity   ON incidents (severity);
CREATE INDEX idx_incidents_status     ON incidents (status);
CREATE INDEX idx_deployments_env      ON deployments (environment);
CREATE INDEX idx_deployments_service  ON deployments (service);
