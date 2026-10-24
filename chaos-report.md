# Informe de Chaos Engineering

## Test 1: Caída de servicio dependiente

- **Escenario**: Crear una orden, detener `catalog-service`, volver a crearla y después reiniciar el catálogo.
- **Impacto esperado**: La orden inicial y la orden posterior a la recuperación responden `200`. Mientras el catálogo está detenido, `orders-service` responde `503 Catalog service unavailable` y no guarda una orden.
- **Tiempo de detección**: La falla se detecta en la primera solicitud que intenta consultar el catálogo. El cliente HTTP tiene un timeout de 2 segundos; una conexión rechazada puede fallar antes.
- **Recuperación**: Al iniciar de nuevo `catalog-service`, las solicitudes vuelven a funcionar sin reiniciar `orders-service`. El almacenamiento de órdenes es en memoria y se pierde si se reinicia el contenedor de órdenes.
- **Tiempo medido**: Completar después de ejecutar `./chaos-test.sh`; depende del equipo y del tiempo de arranque de Docker.

## Test 2: Cambio de contrato sin versionar

- **Escenario**: Cambiar `price_per_hour` por `hourly_rate` en la respuesta de `GET /spaces/{space_id}` y reconstruir los servicios.
- **Impacto esperado**: El catálogo sigue disponible, pero `POST /orders` responde `502` con `Catalog service contract error: invalid space response`. No se crea la orden.
- **Causa raíz**: `orders-service` valida el contrato del catálogo y requiere el campo `price_per_hour`; el cambio no fue versionado ni coordinado entre servicios.
- **Solución propuesta**: Publicar contratos versionados, por ejemplo `/v1/spaces`, validar compatibilidad en CI con pruebas de contrato y desplegar cambios aditivos antes de retirar campos. Restaurar el campo original devuelve la integración a su estado inicial.
- **Resultado observado**: Ejecutar el experimento y completar con el estado HTTP y el resultado real.
