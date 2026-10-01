# De Kind a AWS EKS

Este módulo describe cómo se ejecutaría la plataforma en AWS. **Está validado pero
nunca se aplica**: el CI comprueba en cada PR que pasa `terraform fmt`,
`terraform validate`, tflint y el escaneo de seguridad de Trivy, sin credenciales
ni coste. La decisión está explicada en
[ADR 0001](../../docs/adr/0001-kind-local-en-lugar-de-eks.md).

## Qué cambia y qué no

La plataforma se diseñó para que el salto a la nube solo sustituya la capa de
cluster:

| Pieza | Local (Kind) | AWS | ¿Cambia? |
|---|---|---|---|
| Cluster | `terraform/cluster` (Kind, 1 control-plane + 2 workers) | `terraform/aws/eks`: EKS con node group gestionado (2-4 nodos) | Sí |
| Add-ons | `terraform/addons` (metrics-server por Helm, `--kubelet-insecure-tls`) | Add-on gestionado `metrics-server` de EKS | Sí |
| Plataforma por entorno | `terraform/envs/{dev,prod}` + `modules/platform` | Los mismos, apuntando a otro `kube_context` | **No** |
| Aplicación | `k8s/` (Kustomize) | Los mismos manifiestos | **No** |
| Imagen | `ghcr.io/gabrielpy28/observability-api:<sha>` | La misma imagen | **No** |
| State de Terraform | Local, un archivo por capa | S3 cifrado con bloqueo nativo (`use_lockfile`) | Sí |
| Autenticación del CD | No aplica (cluster efímero en el runner) | OIDC de GitHub → rol de IAM | Sí |

## Qué crea

- **VPC** en 3 zonas de disponibilidad: subredes privadas para los nodos y públicas
  para el NAT y los balanceadores. Incluye flow logs en CloudWatch y deja sin reglas
  el security group por defecto.
- **EKS 1.35**, la misma versión que valida kubeconform en el CI:
  - nodos gestionados (`t3.medium`, de 2 a 4) en subredes privadas;
  - secrets cifrados con KMS (valor por defecto del módulo);
  - logs `api`, `audit` y `authenticator` del control plane.
- **Add-ons de EKS:** `vpc-cni`, `coredns`, `kube-proxy`, `eks-pod-identity-agent`
  y `metrics-server`.
- **Proveedor OIDC de GitHub y rol de IAM** para el pipeline de CD
  (`github-oidc.tf`).

## Decisiones de seguridad

- **Endpoint de la API solo privado.** Los runners alojados por GitHub cambian de
  IP constantemente, así que no es viable abrir el endpoint público solo a sus
  rangos. El CD se ejecutaría en un runner self-hosted dentro de la VPC, y los
  administradores accederían por VPN o AWS SSM.
- **Sin claves de acceso en GitHub.** El pipeline obtiene credenciales temporales
  con OIDC. La confianza del rol se limita a la rama `main` de este repositorio
  (`repo:GabrielPy28/infrastructure-observability-platform:ref:refs/heads/main`).
- **Mínimo privilegio en dos niveles:**
  - en AWS, el rol solo tiene `eks:DescribeCluster` para generar el kubeconfig;
  - en Kubernetes, una *access entry* le da `AmazonEKSEditPolicy` **solo** en los
    namespaces `observability-dev` y `observability-prod`. No puede tocar
    `kube-system` ni recursos de todo el cluster.
- **Excepción documentada:** el security group de los nodos permite salida a
  cualquier destino. Los nodos la necesitan para descargar imágenes y llamar a las
  APIs de AWS. La justificación está en [.trivyignore](../../.trivyignore).

## Coste aproximado

Precios on-demand de `us-east-1` con la configuración por defecto, orientativos:

| Recurso | Coste mensual |
|---|---:|
| Control plane de EKS | ~73 USD |
| 2 × `t3.medium` | ~61 USD |
| NAT gateway (sin contar tráfico) | ~33 USD |
| CloudWatch (logs del control plane y flow logs) | variable |
| **Total** | **~170 USD/mes** |

En el entorno local, el coste es 0. Por eso el proyecto valida este módulo pero
no lo despliega.

## Cómo se desplegaría

1. **Bucket para el state.** Crear un bucket S3 con versionado y cifrado. Copiar
   `backend.hcl.example` como `backend.hcl` y ajustar el nombre del bucket.
2. **Crear el cluster:**
   ```bash
   cd terraform/aws/eks
   terraform init -backend-config=backend.hcl
   terraform plan -out=eks.tfplan
   terraform apply eks.tfplan
   ```
3. **Configurar kubectl** desde la VPC (runner self-hosted, VPN o SSM):
   ```bash
   $(terraform output -raw configure_kubectl)
   ```
   El contexto que se crea se llama como el ARN del cluster.
4. **Plataforma por entorno.** Son las mismas capas que en local, con otro
   contexto y con su state también en S3:
   ```bash
   terraform -chdir=terraform/envs/prod apply \
     -var kube_context=arn:aws:eks:us-east-1:<cuenta>:cluster/devops-platform
   ```
5. **Aplicación.** Mismos manifiestos y misma tarea:
   ```bash
   task k8s:apply ENV=prod IMAGE=ghcr.io/gabrielpy28/observability-api TAG=<sha> \
     KUBE_CONTEXT=arn:aws:eks:us-east-1:<cuenta>:cluster/devops-platform
   ```

## Cambios en el pipeline de CD

El job `e2e` dejaría de crear un cluster efímero y desplegaría en EKS:

```yaml
deploy:
  runs-on: [self-hosted, eks-vpc]   # runner dentro de la VPC
  permissions:
    id-token: write                 # necesario para OIDC
    contents: read
  steps:
    - uses: aws-actions/configure-aws-credentials@<sha>
      with:
        role-to-assume: <output github_actions_role_arn>
        aws-region: us-east-1
    - run: aws eks update-kubeconfig --region us-east-1 --name devops-platform
    - run: task k8s:apply ENV=prod IMAGE="$IMAGE" TAG="$TAG" KUBE_CONTEXT="$(kubectl config current-context)"
```

El `task k8s:smoke` tendría que adaptarse: hoy lee la API key del state local de
Terraform, mientras que en AWS la leería del state remoto o de AWS Secrets Manager.

## Qué más cambiaría en un despliegue real

- **Base de datos:** SQLite empaquetado en la imagen pasaría a RDS PostgreSQL. Solo
  cambia `app/src/db.py` (ver
  [ADR 0002](../../docs/adr/0002-sqlite-de-solo-lectura-en-la-imagen.md)).
- **Secrets:** la API key se gestionaría con AWS Secrets Manager y External Secrets
  Operator, en lugar de generarse en el state de Terraform.
- **Exposición:** AWS Load Balancer Controller con un Ingress o Gateway, en lugar
  de `kubectl port-forward`.
- **Alta disponibilidad de red:** un NAT gateway por zona de disponibilidad
  (`single_nat_gateway = false`).
