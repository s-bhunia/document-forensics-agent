from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
ANTHROPIC_MAX_TOKENS = 16000


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0

    @classmethod
    def from_openai(cls, usage: dict) -> "Usage":
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or prompt + completion)
        billable_output = max(completion, total - prompt)
        cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        return cls(1, prompt, cached, 0, billable_output, billable_output - completion)

    @classmethod
    def from_anthropic(cls, usage: dict) -> "Usage":
        fresh = int(usage.get("input_tokens") or 0)
        read = int(usage.get("cache_read_input_tokens") or 0)
        write = int(usage.get("cache_creation_input_tokens") or 0)
        return cls(1, fresh + read + write, read, write, int(usage.get("output_tokens") or 0), 0)

    def add(self, other: "Usage") -> None:
        for name in asdict(self):
            setattr(self, name, getattr(self, name) + getattr(other, name))

    def cost_usd(self, settings: Settings) -> float:
        fresh = self.input_tokens - self.cached_tokens - self.cache_write_tokens
        write_price = settings.llm_price_cache_write_per_m or settings.llm_price_input_per_m
        return (
            fresh * settings.llm_price_input_per_m
            + self.cached_tokens * settings.llm_price_cached_per_m
            + self.cache_write_tokens * write_price
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


class _BaseClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.usage = Usage()

    def usage_report(self, pages: int) -> dict:
        return self.usage.report(self.settings, pages)


class ChatClient(_BaseClient):
    """OpenAI-compatible chat completions (OpenAI, Gemini, OpenRouter, vLLM...)."""

    @property
    def enabled(self) -> bool:
        return bool(self.settings.llm_api_key and self.settings.llm_model)

    @property
    def model(self) -> str:
        return self.settings.llm_model

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
                self.usage.add(Usage.from_openai(data.get("usage") or {}))
                return data["choices"][0]["message"]
            except (httpx.HTTPError, LLMError, KeyError, ValueError) as exc:
                last_error = exc
                log.warning("LLM call failed (attempt %d): %s", attempt + 1, exc)
                time.sleep(1.5 * (attempt + 1))
        raise LLMError(str(last_error))


def _image_block(url: str) -> dict:
    header, _, data = url.partition(",")
    media_type = header.removeprefix("data:").split(";")[0] or "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def _user_blocks(content: Any) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    blocks = []
    for part in content or []:
        if part.get("type") == "text":
            blocks.append({"type": "text", "text": part["text"]})
        elif part.get("type") == "image_url":
            blocks.append(_image_block(part["image_url"]["url"]))
    return blocks


def _assistant_blocks(message: dict) -> list[dict]:
    if message.get("_anthropic_content"):
        return message["_anthropic_content"]
    blocks = [{"type": "text", "text": message["content"]}] if message.get("content") else []
    for call in message.get("tool_calls") or []:
        fn = call.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        blocks.append({"type": "tool_use", "id": call["id"], "name": fn.get("name", ""), "input": args})
    return blocks


def to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    system_parts: list[str] = []
    out: list[dict] = []
    for message in messages:
        role = message["role"]
        if role == "system":
            system_parts.append(message["content"])
            continue
        if role == "assistant":
            out.append({"role": "assistant", "content": _assistant_blocks(message)})
            continue
        if role == "tool":
            text = str(message.get("content") or "")
            blocks = [{"type": "tool_result", "tool_use_id": message["tool_call_id"], "content": text,
                       **({"is_error": True} if text.startswith("Error:") else {})}]
        else:
            blocks = _user_blocks(message.get("content"))
        if out and out[-1]["role"] == "user":
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": "user", "content": blocks})
    return "\n\n".join(system_parts), out


def to_anthropic_tools(tools: list[dict] | None) -> list[dict]:
    return [
        {"name": t["function"]["name"], "description": t["function"].get("description", ""),
         "input_schema": t["function"]["parameters"]}
        for t in tools or []
    ]


def from_anthropic(response: dict) -> dict:
    blocks = response.get("content") or []
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    calls = [
        {"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {})}}
        for b in blocks if b.get("type") == "tool_use"
    ]
    return {"role": "assistant", "content": text or None, "tool_calls": calls or None, "_anthropic_content": blocks}


class AnthropicChatClient(_BaseClient):
    """Native Claude Messages API through the official SDK; speaks the same message shape as ChatClient."""

    def __init__(self, settings: Settings, sdk: Any = None):
        super().__init__(settings)
        self._sdk = sdk

    @property
    def enabled(self) -> bool:
        return bool(self.settings.anthropic_api_key and self.settings.anthropic_llm_model)

    @property
    def model(self) -> str:
        return self.settings.anthropic_llm_model

    @property
    def sdk(self) -> Any:
        if self._sdk is None:
            import anthropic

            self._sdk = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key,
                base_url=self.settings.anthropic_base_url or "https://api.anthropic.com",
                timeout=self.settings.llm_timeout,
                max_retries=3,
            )
        return self._sdk

    def chat(self, messages: list[dict], tools: list[dict] | None = None, tool_choice: Any = None) -> dict:
        system, converted = to_anthropic(messages)
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "messages": converted,
            "cache_control": {"type": "ephemeral"},
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = to_anthropic_tools(tools)
        if self.settings.anthropic_fallbacks:
            params["betas"] = [ANTHROPIC_FALLBACK_BETA]
            params["fallbacks"] = "default"
        try:
            response = self.sdk.beta.messages.create(**params)
        except Exception as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        data = response.to_dict() if hasattr(response, "to_dict") else dict(response)
        self.usage.add(Usage.from_anthropic(data.get("usage") or {}))
        if data.get("stop_reason") == "refusal":
            log.warning("Claude declined the request: %s", data.get("stop_details"))
        return from_anthropic(data)


def create_client(settings: Settings) -> ChatClient | AnthropicChatClient:
    if settings.llm_provider.lower() == "anthropic":
        return AnthropicChatClient(settings)
    return ChatClient(settings)
