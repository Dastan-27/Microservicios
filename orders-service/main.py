import os
from json import JSONDecodeError

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ValidationError


class Space(BaseModel):
    id: int
    name: str
    city: str
    capacity: int
    price_per_hour: float


class Order(BaseModel):
    id: int
    space_id: int
    space_name: str
    user_email: str
    hours: int
    price_per_hour: float
    total_price: float


app = FastAPI(
    title="Servicio de Órdenes de Coworking",
    description="Gestiona reservas de espacios de coworking. Recibe eventos de disponibilidad desde el consumer-service y mantiene un caché de espacios actualizado.",
    version="1.0.0",
)
CATALOG_SERVICE_URL = os.getenv(
    "CATALOG_SERVICE_URL", "http://localhost:8001"
).rstrip("/")
if not CATALOG_SERVICE_URL.startswith(("http://", "https://")):
    CATALOG_SERVICE_URL = f"https://{CATALOG_SERVICE_URL}"
CATALOG_TIMEOUT_SECONDS = float(os.getenv("CATALOG_TIMEOUT_SECONDS", "2.0"))
orders: list[Order] = []


@app.get("/health", tags=["Salud"], summary="Verificar estado del servicio")
def health() -> dict[str, str]:
    """Devuelve el estado actual del servicio."""
    return {"status": "ok", "service": "orders-service"}


@app.post("/orders", response_model=Order, tags=["Reservas"], summary="Crear una nueva reserva")
async def create_order(
    space_id: int = Query(gt=0, description="ID del espacio a reservar"),
    user_email: str = Query(min_length=3, description="Correo del usuario"),
    hours: int = Query(gt=0, description="Número de horas a reservar"),
) -> Order:
    """Crea una nueva reserva para un espacio de coworking consultando su precio al catalog-service."""
    try:
        async with httpx.AsyncClient(timeout=CATALOG_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{CATALOG_SERVICE_URL}/spaces/{space_id}"
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503, detail="Catalog service unavailable"
        ) from exc

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Coworking space not found")
    if not response.is_success:
        raise HTTPException(
            status_code=502, detail="Catalog service returned an unexpected response"
        )

    try:
        space = Space.model_validate(response.json())
    except (JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Catalog service contract error: invalid space response",
        ) from exc

    order = Order(
        id=len(orders) + 1,
        space_id=space.id,
        space_name=space.name,
        user_email=user_email,
        hours=hours,
        price_per_hour=space.price_per_hour,
        total_price=space.price_per_hour * hours,
    )
    orders.append(order)
    return order


@app.get("/orders", response_model=list[Order], tags=["Reservas"], summary="Listar todas las reservas")
def list_orders() -> list[Order]:
    """Devuelve la lista de todas las reservas realizadas en esta sesión."""
    return orders


SPACES_CACHE: dict = {}


@app.post("/catalog-events", tags=["Eventos"], summary="Recibir evento de disponibilidad")
async def handle_catalog_event(request: Request) -> dict:
    """Recibe notificaciones de cambio de disponibilidad desde el consumer-service (LAB 7) y actualiza el caché interno de espacios."""
    payload = await request.json()
    space_data = payload.get("space_data", {})
    space_id = space_data.get("space_id")
    if space_id:
        SPACES_CACHE[space_id] = space_data
        print(f"[orders-service] Evento recibido: Espacio {space_id} actualizado → {space_data}")
    return {"status": "evento_recibido", "space_id": space_id, "en_cache": SPACES_CACHE.get(space_id)}


@app.get("/spaces-cache", tags=["Eventos"], summary="Ver caché de espacios sincronizados")
def get_spaces_cache() -> dict:
    """Muestra el caché de espacios actualizado por eventos SpaceChanged. Cada entrada corresponde a un espacio cuya disponibilidad fue modificada."""
    return SPACES_CACHE



if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
