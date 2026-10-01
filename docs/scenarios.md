# Escenarios de resiliencia

Cuatro escenarios reproducibles que validan el comportamiento de la plataforma ante
fallos, despliegues defectuosos y picos de carga. Se ejecutan contra el entorno
`prod` del cluster local (HPA de 2 a 4 réplicas, 2 nodos worker).

```bash
task scenario:all            # los cuatro en orden (~8 min)
task scenario:healthy        # 1. despliegue sano
task scenario:pod-failure    # 2. fallo de pod + mantenimiento de nodo
task scenario:bad-deploy     # 3. despliegue defectuoso + rollback
task scenario:autoscaling    # 4. autoescalado bajo carga
```

## Cómo se mide la disponibilidad

Cada escenario levanta un **pod cliente dentro del cluster** que consulta el Service
4 veces por segundo (`GET /api/v1/servers/summary` con API key) y registra cada
código de respuesta. Un `kubectl port-forward` no sirve para esto: se conecta a un
único pod y no refleja lo que ve un consumidor real del Service.

Los pods auxiliares (cliente de tráfico y k6) cumplen el perfil de Pod Security
`restricted` que Terraform impone al namespace: no-root, sin escalada de
privilegios, `capabilities: drop ALL` y `seccomp: RuntimeDefault`.

## Resumen de resultados

| Escenario | Qué se provoca | Peticiones | Errores | Disponibilidad |
|---|---|---:|---:|---:|
| 1. Despliegue sano | — | 63 | 0 | 100 % |
| 2. Fallo de pod y nodo | Borrado de un pod, drain de un nodo, reinicio progresivo | 190 | 0 | 100 % |
| 3. Despliegue defectuoso | Revisión que nunca pasa a Ready + rollback | 545 | 0 | 100 % |
| 4. Autoescalado | 10 usuarios virtuales durante 2m45s (k6) | 13.208 | 0 | 100 % |

Ejecución del 30/09/2026 sobre Kubernetes 1.35 (Kind, 1 control-plane + 2 workers).

---

## 1. Despliegue sano

**Objetivo:** confirmar el estado base, es decir, réplicas mínimas del HPA, repartidas
entre nodos y respondiendo de forma continua.

```text
Réplicas Ready: 2 (HPA min=2, max=4)
Nodos con réplicas: 2 -> devops-platform-worker, devops-platform-worker2
Peticiones: 63 | códigos: {'200': 63} | disponibilidad: 100.00%
```

El reparto entre nodos no es casual: lo pide un `topologySpreadConstraint` en el
Deployment. Si las dos réplicas compartieran nodo, la caída de ese nodo dejaría el
servicio sin réplicas.

## 2. Fallo de pod y mantenimiento de nodo

**2a. Eliminación abrupta de un pod.** El ReplicaSet crea un reemplazo y el Service
solo envía tráfico a pods Ready.

```text
[18:14:31] Eliminando observability-api-57cc5bb9fd-4h7lg
[18:14:40] Réplicas Ready restablecidas en 8.7s
```

**2b. Drain de un nodo (mantenimiento).** `kubectl drain` desaloja los pods del nodo.
El PodDisruptionBudget (`maxUnavailable: 1`) impide desalojar más de una réplica a
la vez, y la réplica se reprograma en el otro worker.

```text
[18:14:40] Drenando devops-platform-worker
[18:14:47] Réplicas tras el drain: {...-bhxsc: worker2, ...-z9b7x: worker2}
[18:14:47] devops-platform-worker vuelve a aceptar pods (uncordon)
```

**2c. Reequilibrio.** Al liberar el nodo, Kubernetes **no mueve** los pods que ya
están en ejecución, así que ambas réplicas quedan en `worker2`. Un
`kubectl rollout restart` las reprograma respetando el `topologySpreadConstraint`.

```text
[18:15:06] Réplicas repartidas en: devops-platform-worker, devops-platform-worker2
Peticiones: 190 | códigos: {'200': 190} | disponibilidad: 100.00%
```

## 3. Despliegue defectuoso y rollback

**Objetivo:** demostrar que una versión rota nunca sustituye a la sana.

Se publica una revisión con `SIMULATE_READINESS_FAILURE=true`: el proceso arranca
(liveness OK), pero `/readyz` responde 503. Tres ajustes del Deployment determinan
el resultado:

| Ajuste | Efecto |
|---|---|
| `maxUnavailable: 0` | No se retira ningún pod sano hasta que el nuevo esté Ready |
| `readinessProbe` en `/readyz` | El pod defectuoso nunca recibe tráfico |
| `progressDeadlineSeconds: 120` | El rollout atascado se marca como fallido |

```text
NAME                                 READY   STATUS    AGE
observability-api-57bb44f689-kbw9j   0/1     Running   22s    <- revisión defectuosa
observability-api-6955ffd7b9-9mb62   1/1     Running   69s    <- revisión sana
observability-api-6955ffd7b9-q7tv4   1/1     Running   81s    <- revisión sana

[18:17:47] Rollout marcado como fallido: ProgressDeadlineExceeded —
           ReplicaSet "observability-api-57bb44f689" has timed out progressing.
[18:17:47] kubectl rollout undo (vuelve a la revisión 10)
Peticiones: 545 | códigos: {'200': 545} | disponibilidad: 100.00%
```

El rollback es instantáneo porque el ReplicaSet sano nunca dejó de funcionar.

El pipeline de CD aplica la misma lógica de forma automática: `task k8s:apply`
ejecuta `rollout undo` y falla si el rollout no progresa.

## 4. Autoescalado bajo carga

**Objetivo:** comprobar que el HPA añade réplicas cuando sube el consumo y que el
servicio mantiene la latencia.

Un pod de k6 ([scripts/load/load-test.js](../scripts/load/load-test.js)) mantiene
10 usuarios virtuales contra `/api/v1/servers?page_size=100&sort=cpu_usage`, una
consulta con JOIN y ordenamiento. El HPA apunta al 70 % de la CPU solicitada, y
metrics-server (instalado por Terraform) le proporciona las métricas.

```text
t=  31s  CPU=  39%  réplicas=2 (deseadas=2)
t=  41s  CPU= 145%  réplicas=2 (deseadas=4)   <- el HPA decide escalar
t=  51s  CPU= 281%  réplicas=4 (deseadas=4)   <- nuevas réplicas Ready
t=  71s  CPU= 135%  réplicas=4 (deseadas=4)   <- la carga se reparte

http_req_failed : 0.00%  (0 de 13.208)
http_req_duration: p(95)=12.28ms  med=6.57ms
```

Las 4 réplicas quedaron repartidas 2 y 2 entre los workers. La reducción a 2 réplicas
se produce unos 5 minutos después de terminar la carga (ventana de estabilización
del HPA), lo que evita oscilaciones si la carga vuelve.

---

## Hallazgos: lo que los escenarios detectaron

Los escenarios no solo confirmaron lo esperado: **destaparon seis problemas reales**
que los tests unitarios, el CI y el smoke test del CD no habían detectado. Todos
están corregidos y verificados.

### 1. Errores 500 bajo concurrencia (bug de la aplicación)

- **Síntoma:** la primera prueba de carga falló con un 75 % de errores 500, aunque
  el HPA escaló correctamente.
- **Causa:** `sqlite3.ProgrammingError: SQLite objects created in a thread can only
  be used in that same thread`. FastAPI ejecuta las dependencias y los endpoints
  síncronos en un pool de hilos, así que la conexión se abría en un hilo y se usaba
  en otro. Con poco tráfico casi siempre se reutilizaba el mismo hilo, y por eso no
  aparecía en los tests ni en el smoke test.
- **Corrección:** `check_same_thread=False` en [db.py](../app/src/db.py). Es seguro
  porque cada conexión la usa una sola petición y la base es de solo lectura.
- **Prevención:** nuevo test de regresión
  ([test_concurrency.py](../app/tests/test_concurrency.py)) con 300 peticiones
  desde 30 hilos. Falla sin la corrección y pasa con ella.

### 2. Una corrección que nunca se desplegó (etiquetado de imágenes)

- **Síntoma:** tras corregir el bug, la prueba de carga seguía fallando.
- **Causa:** los builds con cambios sin commitear se etiquetaban `<sha>-dirty`, así
  que dos imágenes distintas compartían tag. Kubernetes no vio cambios en el
  Deployment y los pods siguieron ejecutando la imagen antigua.
- **Corrección:** el tag de un build con cambios locales incluye un hash del
  contenido del contexto de la imagen (`<sha>-dirty-<hash de app/>`), calculado con
  un índice temporal de git. Imágenes distintas siempre tienen tags distintos.

### 3. Peticiones perdidas al terminar un pod (apagado ordenado)

- **Síntoma:** 1 de 105 peticiones falló justo al iniciar un drain. Era intermitente.
- **Causa:** al terminar un pod, Kubernetes envía `SIGTERM` y, **en paralelo**, lo
  retira de los endpoints del Service. Hasta que kube-proxy actualiza las reglas de
  cada nodo, al pod le pueden llegar conexiones nuevas que uvicorn ya no acepta.
- **Corrección:** `preStop: sleep: 5s` en el Deployment. El pod sigue sirviendo
  mientras el cambio se propaga. Verificado con 3 ejecuciones consecutivas al 100 %.

### 4. Réplicas concentradas en un nodo

- **Síntoma:** tras un rolling update o un drain, las dos réplicas quedaban en el
  mismo nodo.
- **Causa:** el `topologySpreadConstraint` solo actúa al programar un pod, y contaba
  también los pods de la revisión anterior, que estaban a punto de desaparecer.
  Además, Kubernetes no reequilibra pods en ejecución al liberar un nodo.
- **Corrección:** `matchLabelKeys: [pod-template-hash]` (el reparto se calcula por
  revisión) y un `rollout restart` tras el mantenimiento. En un cluster real, un
  *descheduler* automatizaría este reequilibrio.

### 5. Drain fallido y nodos que se quedan acordonados

- **Síntoma:** algunas ejecuciones dejaban los dos workers en `SchedulingDisabled`.
- **Causa:** `kubectl drain` se niega a desalojar pods sin controlador (el cliente
  de tráfico). Si el cliente caía en el nodo elegido, el drain fallaba y el script
  nunca ejecutaba `uncordon`.
- **Corrección:** el drain excluye los pods del escenario (`--pod-selector`) y el
  `uncordon` se ejecuta en un bloque `finally`: un nodo en mantenimiento siempre se
  libera, falle lo que falle.

### 6. Límites del entorno local

- **Síntoma:** una prueba de carga de 30 usuarios virtuales sin pausas saturó la
  máquina virtual de Docker Desktop, que se reinició. Tras el reinicio, el API
  server de Kind dejó de ser accesible desde el equipo.
- **Corrección:** la carga se ajustó a 10 usuarios con 100 ms de pausa, suficiente
  para superar el objetivo del HPA con margen. Además, los scripts reintentan los
  errores transitorios de conexión con el API server.
- **Recuperación:** si ocurre, `docker restart devops-platform-control-plane`
  restablece el reenvío de puertos de Docker Desktop.
