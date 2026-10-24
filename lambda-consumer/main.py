"""
LAB 7: Consumer Service — FastAPI (modo local)
Sustituye al Lambda consumer-fn. Corre en puerto 8003.
Recibe eventos SpaceChanged desde catalog-service y los reenvía a orders-service.
"""
import os
from datetime import datetime, timezone
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# URL del orders-service para notificar cambios
ORDERS_SERVICE_URL = os.environ.get(
    "ORDERS_SERVICE_URL", "http://localhost:8002"
).rstrip("/")

ORDERS_TIMEOUT_SECONDS = float(os.environ.get("ORDERS_TIMEOUT_SECONDS", "3.0"))

app = FastAPI(
    title="Consumer Service (LAB 7)",
    description="Recibe eventos SpaceChanged y notifica a orders-service. Simula Lambda + SQS en local.",
    version="1.0.0",
)

# Historial de eventos procesados (en memoria)
events_log: list[dict] = []


class CatalogEvent(BaseModel):
    source: str
    detail_type: str | None = None
    detail: dict[str, Any]

    class Config:
        populate_by_name = True
        extra = "allow"


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
def health() -> dict:
    """Verifica que el servicio está corriendo."""
    return {"status": "ok", "service": "consumer-service", "port": 8003}


# ---------------------------------------------------------------------------
# EVENTS ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/events", tags=["Events"])
def list_events() -> list[dict]:
    """Lista todos los eventos SpaceChanged recibidos y procesados."""
    return events_log


@app.post("/events", tags=["Events"])
async def receive_event(payload: dict) -> dict:
    """
    Recibe un evento SpaceChanged desde catalog-service.
    Lo registra en el historial y lo reenvía a orders-service.
    """
    source = payload.get("source", "unknown")
    detail_type = payload.get("detail-type", "SpaceChanged")
    detail = payload.get("detail", payload)

    received_at = datetime.now(timezone.utc).isoformat()
    print(f"[consumer-service] Evento recibido [{detail_type}] de [{source}]: {detail}")

    # Notificar a orders-service
    orders_status = "not_notified"
    orders_error = None
    try:
        notification = {
            "event_type": detail_type,
            "source": source,
            "space_data": detail,
            "received_at": received_at,
        }
        async with httpx.AsyncClient(timeout=ORDERS_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{ORDERS_SERVICE_URL}/catalog-events", json=notification)
            resp.raise_for_status()
            orders_status = "notified"
            print(f"[consumer-service] orders-service notificado → HTTP {resp.status_code}")
    except httpx.RequestError as exc:
        orders_error = f"orders-service no disponible: {exc}"
        orders_status = "orders_offline"
        print(f"[consumer-service] {orders_error}")
    except httpx.HTTPStatusError as exc:
        orders_error = f"orders-service respondió {exc.response.status_code}: {exc.response.text}"
        orders_status = "orders_error"
        print(f"[consumer-service] {orders_error}")

    # Guardar en historial
    log_entry = {
        "id": len(events_log) + 1,
        "source": source,
        "detail_type": detail_type,
        "detail": detail,
        "received_at": received_at,
        "orders_status": orders_status,
        "orders_error": orders_error,
    }
    events_log.append(log_entry)

    return {
        "status": "processed",
        "event_id": log_entry["id"],
        "orders_notification": orders_status,
        "orders_error": orders_error,
    }


@app.delete("/events", tags=["Events"])
def clear_events() -> dict:
    """Limpia el historial de eventos (útil para pruebas)."""
    events_log.clear()
    return {"status": "cleared", "message": "Historial de eventos limpiado"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
