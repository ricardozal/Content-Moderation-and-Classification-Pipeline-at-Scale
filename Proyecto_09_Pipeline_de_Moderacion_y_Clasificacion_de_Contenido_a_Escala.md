**PROYECTO FINAL · OPCIÓN 9 de 10**

**Pipeline de Moderación y Clasificación de Contenido a Escala**

*Diseñar para volumen, no para una llamada de demostración*

Fundamentos de Arquitectura LLM · Proyecto Final

**1. Contexto y motivación**

Casi cualquier ejercicio de clase que use un LLM se prueba con una o dos llamadas manuales. En producción, un sistema de moderación o clasificación de contenido procesa cientos o miles de ítems por hora, y ahí aparecen problemas que nunca se ven en una demo: rate limits del proveedor, coherencia de criterio entre llamadas, costo acumulado que crece linealmente con el volumen, y la necesidad de saber, al final del día, qué tan bien funcionó el sistema en agregado (no solo si una llamada individual se vio razonable).

Este proyecto obliga al estudiante a pensar como quien opera un sistema, no como quien lo demuestra: procesar un volumen real, medir su propio desempeño operativo, y justificar las decisiones de configuración de parámetros con el mismo rigor visto en la Sesión 4.

**2. Objetivos de aprendizaje**

- Diseñar un pipeline que procese un volumen no trivial de contenido de forma confiable, no solo una llamada a la vez.

- Implementar manejo explícito de rate limits (backoff, colas, o batching), no simplemente ignorarlos hasta que el sistema falle.

- Medir el propio desempeño operativo del sistema (throughput, tasa de error, costo total) como parte central del entregable, no como un detalle secundario.

**3. Planteamiento del problema**

Construir un sistema que clasifique o modere automáticamente un flujo de contenido de texto (reseñas de producto, comentarios de usuarios, tickets de soporte entrantes — el estudiante elige el dominio), procesando un lote de al menos 50 ítems, con manejo robusto de rate limits, un perfil de parámetros de generación justificado para la tarea, y un reporte final de métricas de desempeño operativo del lote completo.

**4. Alcance funcional (qué debe hacer el sistema)**

- Un pipeline que reciba un lote de contenido (mínimo 50 ítems, sintéticos o reales) y produzca una clasificación o decisión de moderación para cada uno.

- Manejo explícito de rate limiting: el estudiante debe elegir e implementar al menos una estrategia (backoff exponencial ante un 429, una cola con límite de tasa, o batching de solicitudes) y demostrar que funciona ante el límite real del proveedor.

- Uso de un perfil de parámetros de generación específico y justificado para la tarea (ej. temperature baja para consistencia en una tarea de clasificación).

- Un reporte final con métricas de desempeño operativo: throughput (ítems procesados por minuto), tasa de error o de reintento, y costo total del lote procesado.

**5. Requisitos no funcionales**

- El sistema no debe detenerse por completo ante un solo error o rate limit —debe continuar procesando el resto del lote y reportar el incidente aislado.

- El procesamiento del lote completo debe completarse en un tiempo razonable, demostrando algún grado de paralelismo o eficiencia (no necesariamente máxima, pero sí deliberada, no accidental).

**6. Arquitectura sugerida**

- Un módulo de ingesta que reciba o genere el lote de contenido a procesar.

- Un módulo de llamada al LLM con la estrategia de rate limiting elegida claramente encapsulada (para que sea fácil de identificar y explicar en el video).

- Un módulo de agregación de métricas que acumule throughput, errores y costo a lo largo de todo el lote.

**7. Plan de trabajo sugerido (5 fases)**

1.  Fase 1 — Elegir el dominio de clasificación/moderación y preparar (o generar) el lote de al menos 50 ítems.

2.  Fase 2 — Implementar el procesamiento básico sin manejo especial de rate limits, y provocar deliberadamente el límite del proveedor para observar el fallo sin protección (línea base).

3.  Fase 3 — Implementar la estrategia de manejo de rate limiting elegida y volver a correr el lote, confirmando que el sistema ya no falla ante el mismo límite.

4.  Fase 4 — Instrumentar la captura de métricas de desempeño (throughput, errores, costo).

5.  Fase 5 — Correr el lote completo de forma definitiva y documentar los resultados junto con la justificación del perfil de parámetros elegido.

**8. Entregables**

- Repositorio con el pipeline funcional.

- El lote de contenido usado (o el generador sintético, si aplica).

- El reporte final de métricas de desempeño del lote completo.

- Video explicativo de máximo 30 minutos.

**9. Rúbrica de evaluación (100 puntos)**

| **Criterio**                                                                         | **Peso**    | **Qué se evalúa**                                                                                                                                                                         |
|--------------------------------------------------------------------------------------|-------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Funcionalidad y código**                                                           | **30 pts**  | El pipeline procesa el lote completo de forma confiable; la clasificación/moderación producida es razonable y consistente.                                                                |
| **Seguridad y arquitectura**                                                         | **20 pts**  | Manejo seguro de credenciales; límites de \`max_tokens\` configurados explícitamente para controlar costo.                                                                                |
| **Procesamiento a volumen con métricas de desempeño reales (entregable específico)** | **25 pts**  | El manejo de rate limits es demostrable (línea base con fallo vs. solución funcionando); las métricas de throughput, error y costo son medidas reales del lote completo, no estimaciones. |
| **Documentación**                                                                    | **10 pts**  | Se justifica explícitamente el perfil de parámetros elegido para la tarea.                                                                                                                |
| **Video (máx. 30 min)**                                                              | **15 pts**  | Debe mostrarse el procesamiento del lote en vivo (o un fragmento representativo) y explicarse la estrategia de rate limiting con evidencia de que funciona.                               |
| **Total**                                                                            | **100 pts** | *Calificación máxima del proyecto*                                                                                                                                                        |

*La distribución de pesos sigue el estándar del curso: funcionalidad/código 30 pts, seguridad y arquitectura 20 pts, entregable específico del proyecto 25 pts, documentación 10 pts, video explicativo 15 pts.*

**10. Guía para el video (máx. 30 minutos)**

El video debe responder explícitamente estas preguntas, en cualquier orden, mostrando la aplicación funcionando en vivo:

1.  ¿Qué dominio eligieron y cómo prepararon el lote de al menos 50 ítems?

2.  Muestren qué pasa SIN la estrategia de rate limiting (línea base) y luego CON ella activa.

3.  Presenten las métricas finales: throughput, tasa de error, costo total del lote.

4.  ¿Por qué eligieron ese perfil específico de parámetros de generación para esta tarea?

**11. Errores comunes a evitar**

- Probar con un lote pequeño (5-10 ítems) donde el rate limit nunca se activa, y por lo tanto nunca se demuestra realmente que la estrategia de manejo funciona.

- Usar temperature alta en una tarea de clasificación — introduce inconsistencia innecesaria en una tarea que debería ser casi determinista.

- Reportar solo el resultado final del lote sin capturar métricas durante el procesamiento (throughput y errores deben medirse en el momento, no reconstruirse después).

**12. Definición de "terminado" (checklist final)**

- El lote de al menos 50 ítems se procesó completamente sin que el sistema se detuviera por completo ante un error aislado.

- Existe evidencia de que el rate limit del proveedor se alcanzó al menos una vez durante las pruebas y fue manejado correctamente.

- El reporte final incluye throughput, tasa de error y costo total, con números reales del lote procesado.

BSG · Fundamentos de Arquitectura LLM · Proyecto Final
