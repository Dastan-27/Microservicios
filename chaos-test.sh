#!/usr/bin/env bash
set -euo pipefail

ORDERS_URL="${ORDERS_URL:-http://localhost:8002}"
COMPOSE=(docker compose)
response_file="$(mktemp)"
catalog_stopped=0

cleanup() {
  local exit_code=$?
  trap - EXIT
  if [[ "$catalog_stopped" -eq 1 ]] && ! "${COMPOSE[@]}" start catalog-service; then
    echo "Could not restart catalog-service during cleanup" >&2
  fi
  rm -f "$response_file"
  exit "$exit_code"
}
trap cleanup EXIT

wait_for_catalog() {
  for attempt in {1..30}; do
    if curl --silent --fail http://localhost:8001/health >/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "catalog-service did not become healthy within 30 seconds" >&2
  return 1
}

create_order() {
  curl --silent --show-error \
    --output "$response_file" \
    --write-out "%{http_code}" \
    --request POST \
    "$ORDERS_URL/orders?space_id=1&user_email=chaos%40example.com&hours=2"
}

echo "1/4 Creating an order while the catalog is running..."
status="$(create_order)"
if [[ "$status" != "200" ]]; then
  cat "$response_file" >&2
  echo "Expected HTTP 200, received $status" >&2
  exit 1
fi
cat "$response_file"
echo

echo "2/4 Stopping catalog-service..."
"${COMPOSE[@]}" stop catalog-service
catalog_stopped=1

echo "3/4 Checking that orders-service reports the dependency failure..."
status="$(create_order)"
if [[ "$status" != "503" ]] || ! grep -q "Catalog service unavailable" "$response_file"; then
  cat "$response_file" >&2
  echo "Expected HTTP 503 with 'Catalog service unavailable', received $status" >&2
  exit 1
fi
echo "Received HTTP $status: $(cat "$response_file")"

echo "4/4 Restarting catalog-service and checking recovery..."
"${COMPOSE[@]}" start catalog-service
catalog_stopped=0
wait_for_catalog
status="$(create_order)"
if [[ "$status" != "200" ]]; then
  cat "$response_file" >&2
  echo "Expected HTTP 200 after recovery, received $status" >&2
  exit 1
fi
cat "$response_file"
echo
echo "Chaos test passed."
