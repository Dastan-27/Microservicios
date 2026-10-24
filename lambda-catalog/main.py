"""
LAB 6: Catalog Service — FastAPI (modo local)
Sustituye al Lambda catalog-fn. Corre en puerto 8001.
En local no usa EventBridge; publica eventos directamente al consumer-service por HTTP.
"""
import os
from datetime import datetime, timezone

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Path, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# URL del consumer-service (LAB 7) para publicar eventos en modo local
CONSUMER_SERVICE_URL = os.environ.get(
    "CONSUMER_SERVICE_URL", "http://localhost:8003"
).rstrip("/")

CATALOG_TIMEOUT_SECONDS = float(os.environ.get("CATALOG_TIMEOUT_SECONDS", "3.0"))

app = FastAPI(
    title="Servicio de Catálogo (LAB 6)",
    description="Gestiona espacios de coworking y publica eventos **SpaceChanged** al consumer-service (LAB 7) cuando cambia la disponibilidad.",
    version="1.0.0",
)

# Base de datos en memoria
SPACES: dict[int, dict] = {
    1: {"id": 1, "name": "Centro Coworking", "city": "Ciudad de México", "capacity": 40, "price_per_hour": 15.0},
    2: {"id": 2, "name": "Norte Coworking", "city": "Monterrey", "capacity": 25, "price_per_hour": 12.5},
    3: {"id": 3, "name": "Costa Coworking", "city": "Guadalajara", "capacity": 30, "price_per_hour": 10.0},
}


class SpaceCreate(BaseModel):
    name: str
    city: str
    capacity: int
    price_per_hour: float


class AvailabilityUpdate(BaseModel):
    capacity: int
    price_per_hour: float | None = None


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Salud"], summary="Verificar estado del servicio")
def health() -> dict:
    """Devuelve el estado actual del servicio. Úsalo para confirmar que está activo."""
    return {"status": "ok", "service": "catalog-service", "port": 8001}


# ---------------------------------------------------------------------------
# CATALOG ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/catalog", tags=["Catálogo"], summary="Listar todos los espacios")
def list_spaces() -> list[dict]:
    """Devuelve la lista completa de espacios de coworking registrados."""
    return list(SPACES.values())


@app.post("/catalog", tags=["Catálogo"], summary="Crear un nuevo espacio", status_code=201)
async def create_space(space_input: SpaceCreate) -> dict:
    """
    Crea y registra un nuevo espacio de coworking en el catálogo.

    Genera un ID automático, almacena el espacio y emite un evento **SpaceChanged**
    al consumer-service (LAB 7) para sincronizar orders-service.
    """
    new_id = max(SPACES.keys(), default=0) + 1
    new_space = {
        "id": new_id,
        "name": space_input.name,
        "city": space_input.city,
        "capacity": space_input.capacity,
        "price_per_hour": space_input.price_per_hour,
    }
    SPACES[new_id] = new_space

    # Notificar al consumer-service
    event_payload = {
        "source": "coworking.catalog",
        "detail-type": "SpaceChanged",
        "detail": {
            "space_id": new_id,
            "name": new_space["name"],
            "city": new_space["city"],
            "new_capacity": new_space["capacity"],
            "price_per_hour": new_space["price_per_hour"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    consumer_status = "not_notified"
    consumer_error = None
    try:
        async with httpx.AsyncClient(timeout=CATALOG_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{CONSUMER_SERVICE_URL}/events", json=event_payload)
            resp.raise_for_status()
            consumer_status = "notified"
    except httpx.RequestError as exc:
        consumer_error = f"Consumer no disponible: {exc}"
        consumer_status = "consumer_offline"
    except httpx.HTTPStatusError as exc:
        consumer_error = f"Consumer respondió {exc.response.status_code}: {exc.response.text}"
        consumer_status = "consumer_error"

    return {
        "message": "Espacio creado exitosamente",
        "space": new_space,
        "event_published": event_payload["detail"],
        "consumer_notification": consumer_status,
        "consumer_error": consumer_error,
    }


@app.get("/catalog/{space_id}", tags=["Catálogo"], summary="Obtener un espacio por ID")
@app.get("/spaces/{space_id}", tags=["Catálogo"], include_in_schema=False)
def get_space(space_id: int = Path(gt=0)) -> dict:
    """Devuelve los datos de un espacio específico según su ID. Retorna 404 si no existe."""
    space = SPACES.get(space_id)
    if not space:
        raise HTTPException(status_code=404, detail=f"Espacio con id {space_id} no encontrado")
    return space


@app.post("/catalog/{space_id}/availability", tags=["Catálogo"], summary="Actualizar disponibilidad de un espacio")
async def update_availability(
    space_id: int = Path(gt=0),
    body: AvailabilityUpdate = Body(...),
) -> dict:
    """
    Actualiza la capacidad (y opcionalmente el precio) de un espacio de coworking.

    Al guardar el cambio, publica automáticamente un evento **SpaceChanged** al
    consumer-service (LAB 7), que a su vez notifica al orders-service.
    """
    space = SPACES.get(space_id)
    if not space:
        raise HTTPException(status_code=404, detail=f"Espacio con id {space_id} no encontrado")

    # Actualizar estado en memoria
    space["capacity"] = body.capacity
    if body.price_per_hour is not None:
        space["price_per_hour"] = body.price_per_hour

    # Construir el payload del evento (mismo formato que EventBridge)
    event_payload = {
        "source": "coworking.catalog",
        "detail-type": "SpaceChanged",
        "detail": {
            "space_id": space["id"],
            "name": space["name"],
            "city": space["city"],
            "new_capacity": space["capacity"],
            "price_per_hour": space["price_per_hour"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Publicar al consumer-service por HTTP
    consumer_status = "not_notified"
    consumer_error = None
    try:
        async with httpx.AsyncClient(timeout=CATALOG_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{CONSUMER_SERVICE_URL}/events", json=event_payload)
            resp.raise_for_status()
            consumer_status = "notified"
    except httpx.RequestError as exc:
        consumer_error = f"Consumer no disponible: {exc}"
        consumer_status = "consumer_offline"
    except httpx.HTTPStatusError as exc:
        consumer_error = f"Consumer respondió {exc.response.status_code}: {exc.response.text}"
        consumer_status = "consumer_error"

    return {
        "message": "Disponibilidad actualizada",
        "space": space,
        "event_published": event_payload["detail"],
        "consumer_notification": consumer_status,
        "consumer_error": consumer_error,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
