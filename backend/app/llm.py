from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0

    @classmethod
    def from_response(cls, usage: dict) -> "Usage":
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or prompt + completion)
        billable_output = max(completion, total - prompt)
        cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        return cls(1, prompt, cached, billable_output, billable_output - completion)

    def add(self, other: "Usage") -> None:
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.cached_tokens += other.cached_tokens
        self.output_tokens += other.output_tokens
        self.thinking_tokens += other.thinking_tokens

    def cost_usd(self, settings: Settings) -> float:
        fresh = self.input_tokens - self.cached_tokens
        return (
            fresh * settings.llm_price_input_per_m
            + self.cached_tokens * settings.llm_price_cached_per_m
            + self.output_tokens * settings.llm_price_output_per_m
        ) / 1_000_000

    def report(self, settings: Settings, pages: int) -> dict:
        cost = self.cost_usd(settings)
        return {
            **asdict(self),
            "total_tokens": self.input_tokens + self.output_tokens,
            "cost_usd": round(cost, 5),
            "cost_per_page_usd": round(cost / max(pages, 1), 5),
            "prices_per_million": {
                "input": settings.llm_price_input_per_m,
                "cached_input": settings.llm_price_cached_per_m,
                "output": settings.llm_price_output_per_m,
            },
        }


class ChatClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.usage = Usage()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.llm_api_key and self.settings.llm_model)

    @property
    def model(self) -> str:
        return self.settings.llm_model

    def usage_report(self, pages: int) -> dict:
        return self.usage.report(self.settings, pages)

    def chat(self, messages: list[dict], tools: list[dict] | None = None, tool_choice: Any = None) -> dict:
        body: dict[str, Any] = {"model": self.settings.llm_model, "messages": messages, "temperature": 0}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = httpx.post(url, headers=headers, json=body, timeout=self.settings.llm_timeout)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise LLMError(f"HTTP {response.status_code}: {response.text[:200]}")
                response.raise_for_status()
                data = response.json()
                self.usage.add(Usage.from_response(data.get("usage") or {}))
                return data["choices"][0]["message"]
            except (httpx.HTTPError, LLMError, KeyError, ValueError) as exc:
                last_error = exc
                log.warning("LLM call failed (attempt %d): %s", attempt + 1, exc)
                time.sleep(1.5 * (attempt + 1))
        raise LLMError(str(last_error))
