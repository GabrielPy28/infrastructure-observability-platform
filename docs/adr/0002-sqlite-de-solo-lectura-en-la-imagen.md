# ADR 0002 — SQLite de solo lectura empaquetado en la imagen

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

La API sirve datos simulados de infraestructura: datacenters, servidores,
incidentes y despliegues. Necesita una base de datos que permita demostrar SQL
(JOINs, filtros, agregaciones y paginación), pero el foco del proyecto es la
plataforma, no la persistencia.

Una base de datos compartida (PostgreSQL) añadiría un StatefulSet, volúmenes
persistentes, migraciones y backups. Por otro lado, SQLite es un archivo, y con
varias réplicas surge un problema: cada pod tendría su propia copia, y escribir
sobre un volumen compartido no es viable (el storage de Kind es `ReadWriteOnce`).

## Decisión

- La base de datos **se genera en tiempo de build**, en una etapa `seed` del
  Dockerfile multi-stage, con Faker y una semilla fija (`Faker.seed(42)`).
- La imagen final contiene el archivo `infra.db` y **no** contiene Faker.
- La aplicación abre la base en modo **solo lectura e inmutable**
  (`mode=ro&immutable=1`), así que la API es de solo consulta.
- Todo el acceso a datos pasa por un único módulo, `app/src/db.py`.

## Consecuencias

**Positivas**

- **Pods stateless:** todas las réplicas son idénticas, de modo que el rolling
  update, el rollback y el HPA funcionan sin almacenamiento compartido.
- **Reproducibilidad:** el mismo commit genera los mismos datos byte a byte (hay un
  test que lo verifica), y el tag de la imagen identifica tanto el código como los
  datos.
- Compatible con `readOnlyRootFilesystem: true` y con Pod Security `restricted`.
- Migrar a RDS PostgreSQL solo cambia `db.py`.

**Negativas / trade-offs**

- Sin escrituras: no hay `POST` ni `PUT`.
- Cambiar los datos requiere un nuevo build y un nuevo despliegue.
- La prueba de carga destapó que FastAPI usa la conexión desde distintos hilos de
  su pool; se resolvió con `check_same_thread=False`, que es seguro porque la base
  es inmutable (ver [docs/scenarios.md](../scenarios.md)).

## Alternativas consideradas

- **PostgreSQL en el cluster (StatefulSet):** realista, pero añade estado,
  volúmenes y migraciones fuera del foco del proyecto.
- **SQLite en un PersistentVolume compartido:** no viable con varias réplicas
  (`ReadWriteOnce`, bloqueos de SQLite sobre almacenamiento de red).
- **Datos en memoria generados al arrancar:** el arranque sería más lento y no
  determinista por réplica sin una semilla compartida, y Faker estaría en la imagen
  de runtime.
