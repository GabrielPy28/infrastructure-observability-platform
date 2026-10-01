// Prueba de carga para el escenario de autoescalado (se ejecuta dentro del cluster).
// Variables: TARGET (URL base del Service) y API_KEY (inyectada desde el Secret).
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 10 }, // rampa de subida
    { duration: "2m", target: 10 }, // carga sostenida: el HPA debe escalar
    { duration: "15s", target: 0 }, // rampa de bajada
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"], // menos del 1% de errores
    http_req_duration: ["p(95)<1000"], // p95 por debajo de 1s
  },
};

const params = { headers: { "X-API-Key": __ENV.API_KEY } };

export default function () {
  // Consulta costosa: 100 servidores con JOIN y ordenamiento.
  const response = http.get(`${__ENV.TARGET}/api/v1/servers?page_size=100&sort=cpu_usage&order=desc`, params);
  check(response, { "status 200": (r) => r.status === 200 });
  sleep(0.1); // pausa entre peticiones de cada usuario virtual
}
