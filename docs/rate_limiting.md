# Estrategia de rate limiting y evidencia

## El límite del proveedor

El free tier de Gemini limita las solicitudes por modelo. La API lo informa en cada respuesta 429:

```
"code": 429,
"status": "RESOURCE_EXHAUSTED",
"message": "You exceeded your current quota ...
  * Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
    limit: 15, model: gemini-3.5-flash-lite
  Please retry in ..."
```

El límite para `gemini-3.5-flash-lite` en esta cuenta es de **15 solicitudes**. El cuerpo del error también trae un campo `retryDelay` con el tiempo sugerido para reintentar.

## Estrategia elegida

Todo vive en `pipeline/llm_client.py`, en la clase `LLMClient` y la función `backoff_delay`. Combina dos mecanismos:

1. **Límite de concurrencia** (`asyncio.Semaphore`): como máximo 4 llamadas simultáneas. El lote se procesa en paralelo, pero sin lanzar las 60 solicitudes de golpe.
2. **Reintento con backoff exponencial** ante un 429 o un error 5xx:
   - La espera crece así: 1-2 s, 2-4 s, 4-8 s... hasta 60 s, con una parte aleatoria (*jitter*) para que los tickets rechazados no reintenten todos en el mismo instante.
   - Si Gemini envía `retryDelay`, se espera al menos ese tiempo.
   - Hay un máximo de 8 reintentos por ticket. Si se agotan, el ticket queda marcado como `rate_limited` y **el resto del lote sigue**.
   - Los errores que no se arreglan reintentando (400, 401, 404) no se reintentan.

En **modo baseline** el mismo cliente se ejecuta sin semáforo y sin reintentos: las 60 solicitudes salen al mismo tiempo y cada 429 se registra como fallo. Es la línea base que pide el proyecto.

## Evidencia: mismo lote, mismo modelo, mismos parámetros

| | Línea base | Con la estrategia |
|---|---|---|
| Comando | `python run.py --mode baseline` | `python run.py --mode protected` |
| Corrida | `results/2026-10-04_213759_baseline` | `results/2026-10-04_213829_protected` |
| Tickets clasificados | **40 / 60** | **60 / 60** |
| Tasa de error | **33.3 %** | **0 %** |
| 429 recibidos | 20 (ninguno reintentado) | 12 (los 12 recuperados) |
| Tickets que necesitaron reintento | — | 12 (20 %) |
| Llamadas simultáneas máximas | 60 | 4 |
| Duración | 1.2 s | 154.1 s |
| Throughput | No es comparable: un tercio del lote se perdió | **23.4 tickets/min** |
| Costo total | $0.007129 | $0.010644 |

### Línea base: el 429 sin protección

Extracto de `results/2026-10-04_213759_baseline/events.jsonl`. El ticket T022 recibe un 429 y queda como fallido:

```json
{"t": 0.373, "event": "error", "item": "T022", "attempt": 1, "type": "RateLimitError", "retry_after": 0.0, "detail": "{\"error\": {\"code\": 429, \"message\": \"You exceeded..."}
```

Estado final del lote: `{'ok': 40, 'rate_limited': 20}`.

### Con la estrategia: el 429 se maneja

Extracto de `results/2026-10-04_213829_protected/events.jsonl`. El ticket T001 recibe un 429, espera los 30 s que pide Gemini y se clasifica en el segundo intento:

```json
{"t": 0.027,  "event": "request",  "item": "T001", "attempt": 1, "in_flight": 1}
{"t": 0.19,   "event": "error",    "item": "T001", "attempt": 1, "type": "RateLimitError", "retry_after": 30.0}
{"t": 0.19,   "event": "backoff",  "item": "T001", "attempt": 1, "wait": 30.32}
{"t": 30.513, "event": "request",  "item": "T001", "attempt": 2, "in_flight": 3}
{"t": 31.407, "event": "response", "item": "T001", "attempt": 2, "latency": 0.894, "input_tokens": 307, "output_tokens": 35, "cost_usd": 0.0001796}
```

Los `retryDelay` recibidos durante la corrida fueron de 30 s y de 55-56 s. El pipeline siempre los respetó.

## Lectura de los resultados

- **Sin protección el sistema pierde un tercio del lote.** El "throughput" de la línea base (1969 tickets/min) es engañoso: es rápido porque dispara todo a la vez y descarta lo que el proveedor rechaza.
- **Con la estrategia se clasifica el 100 % del lote** a costa de tiempo: el proceso dura lo que permite la cuota del proveedor. Los saltos de unos 30 s y 60 s en el log son las esperas por el límite por minuto.
- **El costo de la versión protegida es mayor** porque procesó 60 tickets en vez de 40, no por los reintentos: un 429 no consume tokens. El costo por ticket clasificado es prácticamente el mismo (unos $0.00018).
- Las métricas no se reconstruyen al final. Cada evento se escribe en `events.jsonl` en el momento en que ocurre, y `summary.json` se calcula con los contadores acumulados durante la corrida.

El reporte completo de ambas corridas está en [reporte_metricas.md](reporte_metricas.md).
