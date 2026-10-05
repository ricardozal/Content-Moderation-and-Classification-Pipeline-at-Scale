import asyncio
import random
import time
from dataclasses import dataclass

import httpx

from pipeline import classifier, config


class RateLimitError(Exception):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class TransientError(Exception):
    pass


class PermanentError(Exception):
    pass


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency: float


def parse_retry_delay(response):
    """Gemini sends the suggested wait inside the error body, e.g. "retryDelay": "34s"."""
    try:
        details = response.json()["error"]["details"]
    except (ValueError, KeyError, TypeError):
        return None
    for detail in details:
        if "retryDelay" in detail:
            try:
                return float(detail["retryDelay"].rstrip("s"))
            except ValueError:
                return None
    return None


async def call_gemini(http, ticket_text):
    body = {
        "systemInstruction": {"parts": [{"text": classifier.SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": classifier.build_user_message(ticket_text)}]}],
        "generationConfig": {
            "temperature": config.TEMPERATURE,
            "topP": config.TOP_P,
            "maxOutputTokens": config.MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": classifier.RESPONSE_SCHEMA,
            "thinkingConfig": {"thinkingLevel": config.THINKING_LEVEL},
        },
    }
    start = time.perf_counter()
    try:
        response = await http.post(
            config.API_URL.format(model=config.MODEL),
            headers={"x-goog-api-key": config.GEMINI_API_KEY},
            json=body,
        )
    except httpx.TransportError as e:
        raise TransientError(f"{type(e).__name__}: {e}") from e
    latency = time.perf_counter() - start

    if response.status_code == 429:
        raise RateLimitError(response.text[:500], parse_retry_delay(response))
    if response.status_code >= 500:
        raise TransientError(f"HTTP {response.status_code}: {response.text[:300]}")
    if response.status_code != 200:
        raise PermanentError(f"HTTP {response.status_code}: {response.text[:300]}")

    data = response.json()
    parts = data["candidates"][0].get("content", {}).get("parts", [])
    usage = data.get("usageMetadata", {})
    return LLMResponse(
        text="".join(part.get("text", "") for part in parts),
        input_tokens=usage.get("promptTokenCount", 0),
        output_tokens=usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0),
        latency=latency,
    )


def backoff_delay(attempt, retry_after=None, base_delay=2.0, max_delay=60.0):
    delay = min(max_delay, base_delay * 2 ** (attempt - 1))
    wait = delay / 2 + random.uniform(0, delay / 2)
    if retry_after is not None:
        wait = max(wait, retry_after + random.uniform(0, 1))
    return wait


class LLMClient:
    """Rate limiting strategy.

    Protected mode: at most `concurrency` requests at the same time, and 429/5xx
    errors are retried with exponential backoff, waiting what the API suggests
    when it sends a retryDelay.
    Baseline mode: every request goes out at once and errors are not retried.
    """

    def __init__(self, call_fn, metrics, protected=True, concurrency=4, max_retries=8,
                 base_delay=2.0, max_delay=60.0):
        self.call_fn = call_fn
        self.metrics = metrics
        self.semaphore = asyncio.Semaphore(concurrency) if protected else None
        self.max_retries = max_retries if protected else 0
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def classify(self, ticket):
        if self.semaphore:
            async with self.semaphore:
                result = await self._classify(ticket)
        else:
            result = await self._classify(ticket)
        self.metrics.item_done(result)
        return result

    async def _classify(self, ticket):
        result = {
            "id": ticket["id"],
            "status": "ok",
            "category": None,
            "priority": None,
            "reason": None,
            "expected_category": ticket["expected_category"],
            "expected_priority": ticket["expected_priority"],
            "attempts": 0,
            "error": None,
        }
        while True:
            result["attempts"] += 1
            attempt = result["attempts"]
            self.metrics.request_started(ticket["id"], attempt)
            try:
                response = await self.call_fn(ticket["text"])
            except (RateLimitError, TransientError) as e:
                self.metrics.request_failed(ticket["id"], attempt, e)
                if attempt > self.max_retries:
                    result["status"] = "rate_limited" if isinstance(e, RateLimitError) else "error"
                    result["error"] = str(e)[:300]
                    return result
                wait = backoff_delay(attempt, getattr(e, "retry_after", None), self.base_delay, self.max_delay)
                self.metrics.backoff(ticket["id"], attempt, wait)
                await asyncio.sleep(wait)
                continue
            except Exception as e:
                self.metrics.request_failed(ticket["id"], attempt, e)
                result["status"] = "error"
                result["error"] = f"{type(e).__name__}: {e}"[:300]
                return result

            self.metrics.request_ok(ticket["id"], attempt, response)
            try:
                result.update(classifier.parse_response(response.text))
            except ValueError as e:
                result["status"] = "invalid_output"
                result["error"] = str(e)
            return result
