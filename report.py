"""Build docs/reporte_metricas.md from the saved runs.

python report.py                       # every run in results/
python report.py <run_name> <run_name> # only these runs
"""
import json
import sys
from datetime import datetime

from pipeline import config


def load_summaries(names):
    if names:
        paths = [config.RESULTS_DIR / name / "summary.json" for name in names]
    else:
        paths = sorted(config.RESULTS_DIR.glob("*/summary.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def pct(value):
    return "—" if value is None else f"{value:.1%}"


def build_report(runs):
    lines = [
        "# Reporte de métricas del lote",
        "",
        f"Generado el {datetime.now():%Y-%m-%d %H:%M}. Modelo: `{runs[-1]['model']}`.",
        "",
        "| Corrida | Modo | Tickets ok | Tasa de error | 429 recibidos | Reintentos | Tickets con reintento "
        "| Throughput (tickets/min) | Duración | Costo total (USD) | Latencia prom. / P95 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        lines.append(
            f"| {r['run']} | {r['mode']} | {r['items_ok']}/{r['items_total']} | {pct(r['error_rate'])} "
            f"| {r['rate_limit_hits']} | {r['retries']} | {pct(r['retry_rate'])} "
            f"| {r['throughput_items_per_min']} | {r['duration_s']} s | ${r['cost_usd']:.6f} "
            f"| {r['latency_avg_s']} s / {r['latency_p95_s']} s |"
        )
    lines += ["", "## Detalle", ""]
    for r in runs:
        lines += [
            f"### {r['run']}",
            "",
            f"- Parámetros: temperature={r['temperature']}, top_p={r['top_p']}, max_output_tokens={r['max_output_tokens']}, thinking_level={r['thinking_level']}",
            f"- Concurrencia máxima configurada: {r['concurrency']} · observada: {r['max_in_flight']} · reintentos máximos: {r['max_retries']}",
            f"- Estados finales: {r['status_counts']}",
            f"- Llamadas totales a la API: {r['requests']} · otros errores: {r['other_errors']} · suma de esperas por backoff (todos los tickets): {r['backoff_seconds']} s",
            f"- Tokens: {r['input_tokens']} de entrada, {r['output_tokens']} de salida",
            f"- Exactitud sobre {r['evaluated_items']} tickets clasificados: categoría {pct(r['category_accuracy'])}, prioridad {pct(r['priority_accuracy'])}",
            f"- Distribución de categorías: {r['category_counts']}",
            "",
        ]
    return "\n".join(lines)


def main():
    runs = load_summaries(sys.argv[1:])
    if not runs:
        raise SystemExit("No runs found in results/")
    report = build_report(runs)
    config.REPORT_FILE.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSaved in {config.REPORT_FILE.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
