"""Classify the ticket batch and save the run metrics.

python run.py --mode baseline     # no rate limit handling
python run.py --mode protected    # concurrency limit + retries with backoff
"""
import argparse
import asyncio
import json
from datetime import datetime
from functools import partial

import httpx

from pipeline import config
from pipeline.ingest import load_tickets
from pipeline.llm_client import LLMClient, call_gemini
from pipeline.metrics import Metrics


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "protected"], default="protected")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-retries", type=int, default=8)
    parser.add_argument("--limit", type=int, help="process only the first N tickets")
    return parser.parse_args()


async def main():
    args = parse_args()
    if not config.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY is missing in .env")

    prices = json.loads(config.PRICES_FILE.read_text(encoding="utf-8"))
    if config.MODEL not in prices:
        raise SystemExit(f"No price for {config.MODEL} in prices.json")

    tickets = load_tickets(limit=args.limit)
    protected = args.mode == "protected"
    started = datetime.now()
    run_dir = config.RESULTS_DIR / f"{started:%Y-%m-%d_%H%M%S}_{args.mode}"
    info = {
        "run": run_dir.name,
        "mode": args.mode,
        "model": config.MODEL,
        "started_at": started.isoformat(timespec="seconds"),
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "max_output_tokens": config.MAX_OUTPUT_TOKENS,
        "thinking_level": config.THINKING_LEVEL,
        "concurrency": args.concurrency if protected else len(tickets),
        "max_retries": args.max_retries if protected else 0,
    }

    print(f"Processing {len(tickets)} tickets | mode={args.mode} | model={config.MODEL}")
    metrics = Metrics(run_dir, len(tickets), info, prices[config.MODEL])
    limits = httpx.Limits(max_connections=100)
    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT, limits=limits) as http:
        client = LLMClient(partial(call_gemini, http), metrics, protected=protected,
                           concurrency=args.concurrency, max_retries=args.max_retries)
        await asyncio.gather(*(client.classify(ticket) for ticket in tickets))

    summary = metrics.close()
    print("\nSummary")
    for key in ("items_ok", "items_failed", "error_rate", "throughput_items_per_min", "rate_limit_hits",
                "retries", "retry_rate", "cost_usd", "duration_s", "category_accuracy", "priority_accuracy"):
        print(f"  {key}: {summary[key]}")
    print(f"\nSaved in results/{run_dir.name}/")


if __name__ == "__main__":
    asyncio.run(main())
