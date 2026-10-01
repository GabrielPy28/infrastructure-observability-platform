# ADR 0007 — Seguridad de la cadena de suministro y del runtime

- **Estado:** Aceptada
- **Fecha:** 2026-09-30

## Contexto

Un pipeline de CD que construye y despliega automáticamente es un objetivo
atractivo: una GitHub Action comprometida, un binario alterado o una imagen
vulnerable llegarían a producción sin intervención humana. Durante el proyecto
vimos dos casos:

- los binarios de la release `v0.66.0` de Trivy dejaron de estar publicados y
  rompieron el CI: las dependencias externas pueden cambiar o desaparecer;
- el escaneo detectó CVEs de OpenSSL en la imagen base con parche disponible.

## Decisión

**Cadena de suministro (CI/CD)**

- Todas las GitHub Actions se fijan por **commit SHA**, con la versión en un
  comentario, porque un tag puede moverse y un SHA no.
- Los binarios descargados en el pipeline (kind, kubeconform) se verifican con
  `sha256sum`.
- Cada job usa permisos mínimos del `GITHUB_TOKEN`: `contents: read` por defecto y
  `packages: write` solo al publicar.
- **Security gates:**
  - Trivy bloquea las vulnerabilidades HIGH/CRITICAL **con parche disponible** en
    la imagen;
  - Trivy también bloquea las misconfigurations HIGH/CRITICAL en Terraform,
    Kubernetes y Dockerfile.
- Las excepciones se documentan con justificación en `.trivyignore`; nunca se
  silencian sin explicación.
- Dependabot actualiza semanalmente las actions, pip, Docker y los providers de
  Terraform, y cada actualización pasa por el CI.

**Imagen y runtime**

- **Imagen:**
  - multi-stage: Faker y las herramientas de build no llegan a la imagen final;
  - usuario no-root con UID numérico (10001);
  - aplica los parches de seguridad de Debian en cada build.
- **Pod:**
  - `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`,
    `capabilities: drop ALL` y `seccomp: RuntimeDefault`;
  - sin token de ServiceAccount.
- **Namespaces** con Pod Security Admission `restricted` (enforce): el cluster
  rechaza los pods que no cumplen.
- **API protegida con `X-API-Key`:**
  - comparación en tiempo constante;
  - una clave distinta por entorno, generada por Terraform;
  - endpoints de salud abiertos para los probes.
- **En AWS** ([terraform/aws](../../terraform/aws/README.md)):
  - OIDC en lugar de claves de acceso;
  - rol limitado a la rama `main`;
  - permisos de edición solo en los namespaces de la aplicación;
  - endpoint de la API privado.

## Consecuencias

**Positivas**

- Un PR no puede integrarse con vulnerabilidades corregibles ni con
  misconfigurations graves.
- El compromiso de un tag de una action de terceros no afecta al pipeline.
- Los mismos controles del CI se pueden ejecutar en local.

**Negativas / trade-offs**

- Fijar por SHA exige actualizar los SHAs; Dependabot lo automatiza.
- El security gate puede bloquear un merge por un CVE nuevo en la imagen base, sin
  ningún cambio en el código (ocurrió en la Fase 4). Es el comportamiento deseado,
  pero requiere atención.
- `apt-get upgrade` en el build hace la imagen menos reproducible entre builds del
  mismo commit, a cambio de incluir siempre los últimos parches.

## Alternativas consideradas

- **Fijar actions por tag:** más legible, pero vulnerable a tags movidos.
- **Ignorar CVEs sin parche y con parche:** aceleraría los merges, pero ocultaría
  riesgos reales y corregibles.
- **Firma de imágenes (cosign) y SBOM:** mejora natural para un siguiente paso; no
  se incluyó para mantener el alcance.
