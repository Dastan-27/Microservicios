# Coworking Serverless - Migración Event-Driven (Clase 3)

Laboratorio de microservicios migrado a arquitectura Serverless dirigida por eventos (Event-Driven Architecture) con AWS SAM, API Gateway, AWS Lambda, Amazon EventBridge y Amazon SQS.

---

## 📐 Arquitectura

```text
[ Cliente HTTP / curl ]
          │
          ▼
   API Gateway (/catalog o /spaces)
          │
          ▼
   Lambda: catalog-fn (LAB 6)
          │  (Publica evento 'SpaceChanged' con boto3)
          ▼
      EventBridge (default bus)
          │  (Regla de filtrado: coworking.catalog / SpaceChanged)
          ▼
   SQS: catalog-events
          │  (Desencadenador de evento / polling)
          ▼
   Lambda: consumer-fn (LAB 7)
          │  (POST /catalog-events)
          ▼
     orders-service (FastAPI / ECS)
```

---

## 📁 Estructura del Proyecto

```text
.
├── template.yaml                  # Plantilla AWS SAM (Infraestructura como Código)
├── docker-compose.yml             # LocalStack (AWS local gratuito) + orders-service
├── lambda-catalog/                # LAB 6: Lambda catalog-service
│   ├── handler.py
│   └── requirements.txt
├── lambda-consumer/               # LAB 7: Lambda consumidor de eventos SQS
│   ├── handler.py
│   └── requirements.txt
├── orders-service/                # Servicio de órdenes en FastAPI
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
└── coworking.postman_collection.json
```

---

## 🚀 Despliegue 100% Gratuito y Local (Sin Cuenta de AWS)

Para no gastar dinero ni ingresar tarjetas en AWS, usamos **LocalStack** para emular API Gateway, Lambda, EventBridge y SQS en tu máquina con Docker.

### 1. Iniciar el entorno local

```bash
docker compose up -d
```

### 2. Construir la plantilla SAM

```bash
sam build
```

### 3. Desplegar en LocalStack

Usando `samlocal` (wrapper gratuito de SAM para LocalStack):

```bash
pip install aws-sam-cli-local
samlocal deploy --stack-name coworking-serverless --resolve-s3
```

---

## 🧪 Pruebas del Flujo Event-Driven

### 1. Consultar espacios (vía API Gateway / Lambda)

```bash
curl http://localhost:4566/_aws/execute-api/catalog
```

### 2. Actualizar disponibilidad (dispara evento a EventBridge)

```bash
curl -X POST "http://localhost:4566/_aws/execute-api/catalog/1/availability" \
  -H "Content-Type: application/json" \
  -d '{"capacity": 15}'
```

**Lo que sucede por debajo:**
1. `catalog-fn` recibe la petición y emite `SpaceChanged` a **EventBridge**.
2. EventBridge filtra el evento y lo deposita en la cola **SQS** `catalog-events`.
3. `consumer-fn` se despierta automáticamente al recibir el mensaje de SQS.
4. `consumer-fn` notifica a `orders-service` en `http://localhost:8002/catalog-events`.

### 3. Verificar en orders-service la sincronización del evento

```bash
curl http://localhost:8002/spaces-cache
```

---

## ☁️ Despliegue en AWS Real (Opcional)

Si más adelante cuentas con acceso a AWS (o AWS Academy / Learner Lab):

```bash
sam build
sam deploy --guided
```
