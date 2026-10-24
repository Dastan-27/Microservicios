# Coworking Workshop

Laboratorio de microservicios con FastAPI: un catálogo de espacios, un servicio de órdenes que consulta el catálogo por HTTP, Docker Compose y experimentos de resiliencia.

## Estructura

```text
.
├── README.md
├── docker-compose.yml
├── chaos-test.sh
├── chaos-report.md
├── architecture-diagram.svg
├── coworking.postman_collection.json
├── catalog-service/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
└── orders-service/
    ├── main.py
    ├── requirements.txt
    └── Dockerfile
```

## Servicios y API

| Servicio | Puerto | Rutas |
| --- | ---: | --- |
| `catalog-service` | 8001 | `GET /health`, `GET /spaces`, `GET /spaces/{space_id}` |
| `orders-service` | 8002 | `GET /health`, `POST /orders`, `GET /orders` |

El catálogo contiene tres espacios de ejemplo. Las órdenes se guardan en memoria y se pierden al reiniciar `orders-service`.

### Ejecutar localmente

En dos terminales, desde la raíz del proyecto:

```bash
cd catalog-service
pip install -r requirements.txt
python main.py
```

```bash
cd orders-service
pip install -r requirements.txt
python main.py
```

Al ejecutar `orders-service` fuera de Docker, el catálogo debe estar disponible en `http://localhost:8001`. Puedes configurar otro destino mediante `CATALOG_SERVICE_URL`.

Prueba las rutas:

```bash
curl http://localhost:8001/health
curl http://localhost:8001/spaces
curl http://localhost:8001/spaces/1
curl -X POST "http://localhost:8002/orders?space_id=1&user_email=test@example.com&hours=2"
curl http://localhost:8002/orders
```

La creación de una orden consulta el espacio en el catálogo y calcula `total_price`. Si el catálogo no responde, la orden devuelve HTTP `503`; si devuelve un espacio con un contrato incompatible, devuelve HTTP `502`.

## Docker Compose

Desde la raíz del proyecto:

```bash
docker compose up --build
```

Compose crea una red compartida (`coworking_coworking-network`) y configura `orders-service` para llamar al host interno `catalog-service:8001`. El servicio de órdenes espera a que el healthcheck del catálogo pase antes de iniciar.

En otra terminal:

```bash
curl http://localhost:8001/spaces
curl -X POST "http://localhost:8002/orders?space_id=1&user_email=test@example.com&hours=2"
curl http://localhost:8002/orders
```

Para detener los contenedores:

```bash
docker compose down
```

## Lab 4: caída del catálogo

Con los contenedores levantados, ejecuta desde Bash, WSL o Git Bash:

```bash
chmod +x chaos-test.sh
./chaos-test.sh
```

El script verifica la creación de una orden con el catálogo disponible (`200`), detiene solo `catalog-service`, comprueba el `503` y, finalmente, inicia el catálogo y comprueba la recuperación (`200`). El script vuelve a iniciar el catálogo si falla la aserción de indisponibilidad.

## Lab 5: cambio incompatible del contrato

1. En `catalog-service/main.py`, cambia el campo `price_per_hour` del espacio por `hourly_rate` en el modelo y en los datos de ejemplo.
2. Reconstruye y levanta los servicios:

   ```bash
   docker compose up --build -d
   ```

3. Envía una orden. La respuesta esperada es HTTP `502` porque el catálogo ya no cumple el contrato que `orders-service` valida:

   ```bash
   curl -i -X POST "http://localhost:8002/orders?space_id=1&user_email=contract%40test.com&hours=2"
   ```

4. Restaura `price_per_hour` para volver a la versión funcional.
5. Registra los resultados observados en [chaos-report.md](./chaos-report.md).

## Herramientas de diagnóstico

```bash
docker compose logs -f
docker compose ps
docker compose exec orders-service sh
docker network ls
docker network inspect coworking_coworking-network
docker compose exec orders-service python -c "import urllib.request; print(urllib.request.urlopen('http://catalog-service:8001/health').read().decode())"
docker compose build --no-cache
```

La imagen `python:3.11-slim` no incluye necesariamente `bash` ni `ping`; por eso se usa `sh` y una solicitud HTTP con la biblioteca estándar para comprobar la conectividad entre contenedores.

## Colección Postman

Importa [coworking.postman_collection.json](./coworking.postman_collection.json) en Postman. La colección incluye healthchecks, consulta de espacios y creación/listado de órdenes; usa `catalog_url` y `orders_url` como variables de colección.
# Microservicios
