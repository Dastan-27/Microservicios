import json
import os
from datetime import datetime
import boto3

# Configurar cliente EventBridge (detecta LocalStack o AWS automáticamente)
endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
if not endpoint_url and os.environ.get("LOCALSTACK_HOSTNAME"):
    endpoint_url = f"http://{os.environ['LOCALSTACK_HOSTNAME']}:4566"

eventbridge = boto3.client("events", endpoint_url=endpoint_url)
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")

# Espacios de Coworking (almacenamiento en memoria para la función)
SPACES = {
    1: {
        "id": 1,
        "name": "Centro Coworking",
        "city": "Ciudad de México",
        "capacity": 40,
        "price_per_hour": 15.0,
    },
    2: {
        "id": 2,
        "name": "Norte Coworking",
        "city": "Monterrey",
        "capacity": 25,
        "price_per_hour": 12.5,
    },
    3: {
        "id": 3,
        "name": "Costa Coworking",
        "city": "Guadalajara",
        "capacity": 30,
        "price_per_hour": 10.0,
    },
}


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    """
    LAB 6: Lambda catalog-service
    Maneja solicitudes de API Gateway (/catalog y /spaces)
    Publica evento 'SpaceChanged' a EventBridge cuando cambia la disponibilidad.
    """
    http_method = event.get("httpMethod", "GET").upper()
    path = event.get("path", "")
    path_parameters = event.get("pathParameters") or {}
    space_id_raw = path_parameters.get("id")

    # Extraer ID desde query params o path si no vino en pathParameters
    if not space_id_raw and "/" in path:
        parts = [p for p in path.split("/") if p]
        for part in parts:
            if part.isdigit():
                space_id_raw = part
                break

    space_id = int(space_id_raw) if space_id_raw and space_id_raw.isdigit() else None

    # 1. GET /catalog o /spaces (Listar todos los espacios)
    if http_method == "GET" and (not space_id or path.endswith(("/catalog", "/spaces"))):
        return _response(200, list(SPACES.values()))

    # 2. GET /catalog/{id} o /spaces/{id} (Consultar un espacio)
    if http_method == "GET" and space_id:
        space = SPACES.get(space_id)
        if space:
            return _response(200, space)
        return _response(404, {"detail": f"Espacio con id {space_id} no encontrado"})

    # 3. POST /catalog/{id}/availability o /spaces/{id}/availability (Cambio de disponibilidad)
    if http_method in ("POST", "PUT") and space_id:
        space = SPACES.get(space_id)
        if not space:
            return _response(404, {"detail": f"Espacio con id {space_id} no encontrado"})

        body = {}
        if event.get("body"):
            try:
                body = json.loads(event["body"])
            except Exception:
                pass

        new_capacity = body.get("capacity", max(0, space["capacity"] - 1))
        new_price = body.get("price_per_hour", space["price_per_hour"])

        # Actualizar espacio
        space["capacity"] = new_capacity
        space["price_per_hour"] = new_price

        # Publicar evento SpaceChanged en EventBridge
        event_payload = {
            "space_id": space["id"],
            "name": space["name"],
            "city": space["city"],
            "new_capacity": new_capacity,
            "price_per_hour": new_price,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            response = eventbridge.put_events(
                Entries=[
                    {
                        "Source": "coworking.catalog",
                        "DetailType": "SpaceChanged",
                        "Detail": json.dumps(event_payload),
                        "EventBusName": EVENT_BUS_NAME,
                    }
                ]
            )
            return _response(
                200,
                {
                    "message": "Disponibilidad actualizada y evento publicado exitosamente en EventBridge",
                    "event_published": event_payload,
                    "eventbridge_response": response,
                },
            )
        except Exception as exc:
            return _response(
                500,
                {
                    "detail": f"Error al publicar evento en EventBridge: {str(exc)}",
                    "event_payload": event_payload,
                },
            )

    return _response(404, {"detail": f"Ruta no encontrada: {http_method} {path}"})
