import json
import statistics
import time
from collections import Counter

from pipeline.llm_client import RateLimitError


class Metrics:
    """Collects metrics while the batch runs and writes every event to disk as it happens."""

    def __init__(self, run_dir, total_items, info, price, verbose=True):
        run_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir = run_dir
        self.total_items = total_items
        self.info = info
        self.price = price
        self.verbose = verbose
        self.start = time.monotonic()
        self.events_file = open(run_dir / "events.jsonl", "w", encoding="utf-8")
        self.items_file = open(run_dir / "items.jsonl", "w", encoding="utf-8")

        self.requests = 0
        self.retries = 0
        self.rate_limit_hits = 0
        self.other_errors = 0
        self.in_flight = 0
        self.max_in_flight = 0
        self.backoff_seconds = 0.0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.latencies = []

        self.items_done = 0
        self.status_counts = Counter()
        self.items_retried = 0
        self.category_counts = Counter()
        self.evaluated = 0
        self.category_hits = 0
        self.priority_hits = 0

    def elapsed(self):
        return time.monotonic() - self.start

    def log_event(self, kind, **data):
        self.events_file.write(json.dumps({"t": round(self.elapsed(), 3), "event": kind, **data}, ensure_ascii=False) + "\n")
        self.events_file.flush()

    def say(self, message):
        if self.verbose:
            print(f"[{self.elapsed():7.2f}s] {message}", flush=True)

    def request_started(self, item_id, attempt):
        self.requests += 1
        if attempt > 1:
            self.retries += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.log_event("request", item=item_id, attempt=attempt, in_flight=self.in_flight)

    def request_ok(self, item_id, attempt, response):
        self.in_flight -= 1
        cost = (response.input_tokens * self.price["input_per_million"]
                + response.output_tokens * self.price["output_per_million"]) / 1_000_000
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.cost_usd += cost
        self.latencies.append(response.latency)
        self.log_event("response", item=item_id, attempt=attempt, latency=round(response.latency, 3),
                       input_tokens=response.input_tokens, output_tokens=response.output_tokens, cost_usd=cost)

    def request_failed(self, item_id, attempt, error):
        self.in_flight -= 1
        if isinstance(error, RateLimitError):
            self.rate_limit_hits += 1
            self.say(f"429 on {item_id} (attempt {attempt})")
        else:
            self.other_errors += 1
            self.say(f"error on {item_id} (attempt {attempt}): {str(error)[:100]}")
        self.log_event("error", item=item_id, attempt=attempt, type=type(error).__name__,
                       retry_after=getattr(error, "retry_after", None), detail=str(error)[:500])

    def backoff(self, item_id, attempt, wait):
        self.backoff_seconds += wait
        self.log_event("backoff", item=item_id, attempt=attempt, wait=round(wait, 2))
        self.say(f"{item_id} waits {wait:.1f}s before attempt {attempt + 1}")

    def item_done(self, result):
        self.items_done += 1
        self.status_counts[result["status"]] += 1
        if result["attempts"] > 1:
            self.items_retried += 1
        if result["status"] == "ok":
            self.category_counts[result["category"]] += 1
            if result["expected_category"]:
                self.evaluated += 1
                self.category_hits += result["category"] == result["expected_category"]
                self.priority_hits += result["priority"] == result["expected_priority"]
        self.items_file.write(json.dumps({"t": round(self.elapsed(), 3), **result}, ensure_ascii=False) + "\n")
        self.items_file.flush()

        ok = self.status_counts["ok"]
        minutes = self.elapsed() / 60
        self.say(f"[{self.items_done:>2}/{self.total_items}] {result['id']} {result['status']:<14} "
                 f"attempts={result['attempts']} | ok={ok} failed={self.items_done - ok} "
                 f"429s={self.rate_limit_hits} | {ok / minutes:.1f} items/min | ${self.cost_usd:.6f}")

    def summary(self):
        duration = self.elapsed()
        ok = self.status_counts["ok"]
        failed = self.items_done - ok
        latencies = sorted(self.latencies)
        p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 2 else (latencies[0] if latencies else 0)
        return {
            **self.info,
            "duration_s": round(duration, 1),
            "items_total": self.total_items,
            "items_ok": ok,
            "items_failed": failed,
            "status_counts": dict(self.status_counts),
            "error_rate": round(failed / self.items_done, 4) if self.items_done else 0,
            "throughput_items_per_min": round(ok / (duration / 60), 2) if duration else 0,
            "requests": self.requests,
            "rate_limit_hits": self.rate_limit_hits,
            "other_errors": self.other_errors,
            "retries": self.retries,
            "items_retried": self.items_retried,
            "retry_rate": round(self.items_retried / self.items_done, 4) if self.items_done else 0,
            "backoff_seconds": round(self.backoff_seconds, 1),
            "max_in_flight": self.max_in_flight,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "latency_avg_s": round(statistics.mean(latencies), 3) if latencies else 0,
            "latency_p95_s": round(p95, 3),
            "evaluated_items": self.evaluated,
            "category_accuracy": round(self.category_hits / self.evaluated, 4) if self.evaluated else None,
            "priority_accuracy": round(self.priority_hits / self.evaluated, 4) if self.evaluated else None,
            "category_counts": dict(self.category_counts.most_common()),
        }

    def close(self):
        self.events_file.close()
        self.items_file.close()
        summary = self.summary()
        (self.run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
