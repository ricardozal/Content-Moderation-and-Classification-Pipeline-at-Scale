# Reporte de métricas del lote

Generado el 2026-10-04 21:41. Modelo: `gemini-3.5-flash-lite`.

| Corrida | Modo | Tickets ok | Tasa de error | 429 recibidos | Reintentos | Tickets con reintento | Throughput (tickets/min) | Duración | Costo total (USD) | Latencia prom. / P95 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-04_213759_baseline | baseline | 40/60 | 33.3% | 20 | 0 | 0.0% | 1969.69 | 1.2 s | $0.007129 | 0.934 s / 1.129 s |
| 2026-10-04_213829_protected | protected | 60/60 | 0.0% | 12 | 12 | 20.0% | 23.37 | 154.1 s | $0.010644 | 0.733 s / 0.992 s |

## Detalle

### 2026-10-04_213759_baseline

- Parámetros: temperature=0.0, top_p=1.0, max_output_tokens=120, thinking_level=minimal
- Concurrencia máxima configurada: 60 · observada: 60 · reintentos máximos: 0
- Estados finales: {'rate_limited': 20, 'ok': 40}
- Llamadas totales a la API: 60 · otros errores: 0 · suma de esperas por backoff (todos los tickets): 0.0 s
- Tokens: 12029 de entrada, 1408 de salida
- Exactitud sobre 40 tickets clasificados: categoría 92.5%, prioridad 85.0%
- Distribución de categorías: {'hardware': 9, 'software': 8, 'email': 7, 'network': 6, 'access': 5, 'printing': 5}

### 2026-10-04_213829_protected

- Parámetros: temperature=0.0, top_p=1.0, max_output_tokens=120, thinking_level=minimal
- Concurrencia máxima configurada: 4 · observada: 4 · reintentos máximos: 8
- Estados finales: {'ok': 60}
- Llamadas totales a la API: 72 · otros errores: 0 · suma de esperas por backoff (todos los tickets): 569.5 s
- Tokens: 18013 de entrada, 2096 de salida
- Exactitud sobre 60 tickets clasificados: categoría 95.0%, prioridad 88.3%
- Distribución de categorías: {'software': 12, 'hardware': 10, 'network': 10, 'email': 10, 'printing': 10, 'access': 8}
