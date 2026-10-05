# Clasificación de tickets de soporte de TI a escala

Proyecto Final, opción 9: **Pipeline de Moderación y Clasificación de Contenido a Escala**, del curso Fundamentos de Arquitectura LLM.
El enunciado está en [`Proyecto_09_Pipeline_de_Moderacion_y_Clasificacion_de_Contenido_a_Escala.md`](./Proyecto_09_Pipeline_de_Moderacion_y_Clasificacion_de_Contenido_a_Escala.md).

El sistema recibe un lote de 60 tickets de la mesa de ayuda de TI y, con Gemini (`gemini-3.5-flash-lite`), les asigna una **categoría** (hardware, software, red, accesos, correo, impresión) y una **prioridad** (alta, media o baja). Respeta los límites de uso de la API y mide su propio desempeño mientras procesa el lote.

## Arquitectura

```
data/tickets.jsonl ──► ingest.py ──► llm_client.py ──► Gemini API
                                         │  (estrategia de rate limiting)
                                         ▼
                                     metrics.py ──► results/<corrida>/ ──► report.py ──► docs/reporte_metricas.md
```

| Módulo | Qué hace |
|---|---|
| `pipeline/ingest.py` | Lee el lote de tickets y recorta los textos demasiado largos. |
| `pipeline/classifier.py` | Define las categorías, las prioridades, el prompt y el esquema JSON de la respuesta, y valida lo que contesta el modelo. |
| `pipeline/llm_client.py` | Llama a la API de Gemini y aplica la **estrategia de rate limiting**: limita las llamadas simultáneas y reintenta con backoff exponencial. |
| `pipeline/metrics.py` | Acumula throughput, errores, reintentos, tokens y costo durante la corrida y guarda cada evento en disco al momento. |
| `pipeline/config.py` | Modelo, parámetros de generación y rutas. La API key se lee del archivo `.env`. |
| `run.py` | Procesa el lote en modo `baseline` o `protected`. |
| `report.py` | Arma el reporte comparativo a partir de las corridas guardadas. |

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # y pegar la API key de Google AI Studio
```

## Uso

```bash
python run.py --mode baseline                   # línea base: todo en paralelo y sin reintentos
python run.py --mode protected                  # con la estrategia de rate limiting
python run.py --mode protected --concurrency 2  # cambiar el número de llamadas simultáneas
python report.py                                # genera docs/reporte_metricas.md
pytest                                          # pruebas de la estrategia, sin llamar a la API
```

Cada corrida crea `results/<fecha>_<modo>/` con:

- `events.jsonl`: cada llamada, 429, espera y respuesta, con el segundo exacto en que ocurrió.
- `items.jsonl`: el resultado de cada ticket (categoría, prioridad, intentos y estado).
- `summary.json`: las métricas del lote completo.

## Documentación

- [Justificación del perfil de parámetros](docs/parametros.md)
- [Estrategia de rate limiting y evidencia](docs/rate_limiting.md)
- [Reporte de métricas del lote](docs/reporte_metricas.md)

## Resultados

| | Línea base | Con la estrategia |
|---|---|---|
| Tickets clasificados | 40 / 60 | 60 / 60 |
| Tasa de error | 33.3 % | 0 % |
| 429 recibidos | 20 (perdidos) | 12 (recuperados) |
| Throughput | — | 23.4 tickets/min |
| Costo total | $0.007129 | $0.010644 |
| Exactitud categoría / prioridad | 92.5 % / 85.0 % | 95.0 % / 88.3 % |

## Seguridad

- La API key solo vive en `.env`, que está en `.gitignore`. Viaja en el header `x-goog-api-key`, no en la URL, para que no aparezca en logs.
- `max_output_tokens = 120` limita el costo de cada llamada, y los tickets se recortan a 2000 caracteres.
- El prompt indica al modelo que no siga instrucciones escritas dentro del ticket. El lote incluye un intento de ese tipo (T030).
