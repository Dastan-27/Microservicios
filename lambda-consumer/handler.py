import json
import os
import urllib.request
import urllib.error
from datetime import datetime
import boto3

# URL destino para notificar a orders-service
ORDERS_SERVICE_URL = os.environ.get(
    "ORDERS_SERVICE_URL", "http://host.docker.internal:8002"
).rstrip("/")


def lambda_handler(event, context):
    """
    LAB 7: Consumer Lambda que recibe eventos
    Se dispara automáticamente desde la cola SQS catalog-events.
    Lee los eventos originados en EventBridge (SpaceChanged) y notifica a orders-service.
    """
    records = event.get("Records", [])
    print(f"[{datetime.utcnow().isoformat()}] Consumer Lambda activada con {len(records)} eventos de SQS")

    processed = []

    for record in records:
        message_id = record.get("messageId")
        raw_body = record.get("body", "{}")

        try:
            body = json.loads(raw_body)
        except Exception:
            body = {"raw": raw_body}

        # Cuando EventBridge envía a SQS, el payload de la app viene en el campo 'detail'
        detail = body.get("detail", body)
        detail_type = body.get("detail-type", "SpaceChanged")
        source = body.get("source", "coworking.catalog")

        print(f"--> Procesando mensaje [{message_id}] de [{source}] tipo [{detail_type}]")
        print(f"    Detalle del evento: {json.dumps(detail, indent=2)}")

        # Notificar a orders-service a través del endpoint de eventos
        target_endpoint = f"{ORDERS_SERVICE_URL}/catalog-events"
        notification_payload = json.dumps(
            {
                "event_type": detail_type,
                "source": source,
                "space_data": detail,
                "received_at": datetime.utcnow().isoformat(),
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            target_endpoint,
            data=notification_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        notification_status = "notified"
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                print(f"    orders-service respondió: HTTP {resp.status}")
        except urllib.error.URLError as err:
            notification_status = f"skipped/offline ({err.reason})"
            print(f"    orders-service no disponible ({err.reason}), evento procesado localmente en consumidor")

        processed.append(
            {
                "message_id": message_id,
                "space_id": detail.get("space_id") if isinstance(detail, dict) else None,
                "notification_status": notification_status,
            }
        )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "status": "success",
                "processed_records": len(processed),
                "details": processed,
            }
        ),
    }
