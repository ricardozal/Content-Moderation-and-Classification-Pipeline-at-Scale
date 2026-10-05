import asyncio
import json
import random

from pipeline.classifier import parse_response
from pipeline.llm_client import LLMClient, LLMResponse, PermanentError, RateLimitError, backoff_delay
from pipeline.metrics import Metrics

OK_TEXT = '{"category": "network", "priority": "high", "reason": "test"}'
PRICE = {"input_per_million": 0.10, "output_per_million": 0.40}
TICKET = {"id": "T001", "text": "no hay internet", "expected_category": "network", "expected_priority": "high"}


class FakeApi:
    def __init__(self, errors=(), text=OK_TEXT, delay=0.0):
        self.errors = list(errors)
        self.text = text
        self.delay = delay
        self.calls = 0
        self.in_flight = 0
        self.max_in_flight = 0

    async def __call__(self, ticket_text):
        self.calls += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
            if self.errors:
                raise self.errors.pop(0)
            return LLMResponse(self.text, 100, 20, self.delay)
        finally:
            self.in_flight -= 1


def run_batch(api, tickets, tmp_path, **client_args):
    async def main():
        metrics = Metrics(tmp_path / "run", len(tickets), {}, PRICE, verbose=False)
        client = LLMClient(api, metrics, base_delay=0.001, max_delay=0.01, **client_args)
        results = await asyncio.gather(*(client.classify(t) for t in tickets))
        return results, metrics.close()

    return asyncio.run(main())


def make_tickets(n):
    return [{**TICKET, "id": f"T{i:03d}"} for i in range(n)]


def test_retries_after_429_and_succeeds(tmp_path):
    api = FakeApi(errors=[RateLimitError("429"), RateLimitError("429")])
    [result], summary = run_batch(api, [TICKET], tmp_path)
    assert result["status"] == "ok" and result["attempts"] == 3
    assert summary["rate_limit_hits"] == 2 and summary["retries"] == 2
    assert summary["category_accuracy"] == 1.0


def test_baseline_does_not_retry(tmp_path):
    api = FakeApi(errors=[RateLimitError("429")])
    [result], summary = run_batch(api, [TICKET], tmp_path, protected=False)
    assert result["status"] == "rate_limited" and api.calls == 1
    assert summary["error_rate"] == 1.0


def test_permanent_error_is_not_retried(tmp_path):
    api = FakeApi(errors=[PermanentError("HTTP 400")])
    [result], _ = run_batch(api, [TICKET], tmp_path)
    assert result["status"] == "error" and api.calls == 1


def test_failed_ticket_does_not_stop_the_batch(tmp_path):
    api = FakeApi(errors=[RateLimitError("429")] * 3)
    results, summary = run_batch(api, make_tickets(2), tmp_path, concurrency=1, max_retries=2)
    assert [r["status"] for r in results] == ["rate_limited", "ok"]
    assert summary["items_ok"] == 1 and summary["items_failed"] == 1


def test_concurrency_limit(tmp_path):
    api = FakeApi(delay=0.01)
    _, summary = run_batch(api, make_tickets(20), tmp_path, concurrency=3)
    assert api.max_in_flight == 3 and summary["max_in_flight"] == 3


def test_baseline_sends_everything_at_once(tmp_path):
    api = FakeApi(delay=0.01)
    run_batch(api, make_tickets(20), tmp_path, protected=False)
    assert api.max_in_flight == 20


def test_cost_uses_real_tokens(tmp_path):
    _, summary = run_batch(FakeApi(), make_tickets(10), tmp_path)
    assert summary["input_tokens"] == 1000 and summary["output_tokens"] == 200
    assert abs(summary["cost_usd"] - (1000 * 0.10 + 200 * 0.40) / 1_000_000) < 1e-12


def test_events_are_written_in_order(tmp_path):
    run_batch(FakeApi(errors=[RateLimitError("429", retry_after=0.001)]), [TICKET], tmp_path)
    lines = (tmp_path / "run" / "events.jsonl").read_text().splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["request", "error", "backoff", "request", "response"]


def test_backoff_uses_retry_delay():
    assert 30 <= backoff_delay(1, retry_after=30) <= 31


def test_backoff_grows_until_max():
    random.seed(0)
    for attempt, ceiling in [(1, 2), (2, 4), (3, 8), (4, 16), (10, 60)]:
        assert ceiling / 2 <= backoff_delay(attempt, base_delay=2, max_delay=60) <= ceiling


def test_parse_response_rejects_unknown_labels():
    assert parse_response(OK_TEXT)["category"] == "network"
    for bad in ['{"category": "other", "priority": "high"}', "not json"]:
        try:
            parse_response(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad}")
