import httpx
import pytest

from app.config import Settings
from app.llm import ChatClient, LLMError


class _Response:
    def __init__(self, status: int = 200, message: dict | None = None):
        self.status_code, self.text = status, "body"
        self._message = message or {"role": "assistant", "content": "hi"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return {"choices": [{"message": self._message}]}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.llm.time.sleep", lambda s: None)
    return ChatClient(Settings(llm_api_key="k", llm_model="m", llm_base_url="https://llm.example/v1/"))


def test_disabled_without_key():
    assert not ChatClient(Settings(llm_api_key="", llm_model="")).enabled


def test_chat_sends_openai_compatible_request(client, monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json)
        return _Response(message={"role": "assistant", "tool_calls": [{"id": "1"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    reply = client.chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])
    assert reply["tool_calls"] == [{"id": "1"}]
    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer k"
    assert captured["body"]["model"] == "m" and captured["body"]["tool_choice"] == "auto"


def test_usage_counts_thinking_as_output_and_prices_it(client, monkeypatch):
    class WithUsage(_Response):
        def json(self):
            return {"choices": [{"message": self._message}],
                    "usage": {"prompt_tokens": 1235, "completion_tokens": 62, "total_tokens": 1967,
                              "prompt_tokens_details": {"cached_tokens": 235}}}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: WithUsage())
    client.chat([])
    client.chat([])
    usage = client.usage
    assert (usage.calls, usage.input_tokens, usage.cached_tokens) == (2, 2470, 470)
    assert usage.output_tokens == 2 * 732 and usage.thinking_tokens == 2 * 670
    report = client.usage_report(pages=2)
    expected = (2000 * 2.0 + 470 * 0.1 + 1464 * 10.0) / 1_000_000
    assert report["cost_usd"] == round(expected, 5)
    assert report["cost_per_page_usd"] == round(expected / 2, 5)
    assert report["total_tokens"] == 2470 + 1464


def test_chat_retries_transient_errors(client, monkeypatch):
    responses = iter([_Response(503), _Response(200)])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: next(responses))
    assert client.chat([])["content"] == "hi"


def test_chat_raises_after_retries(client, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(LLMError):
        client.chat([])


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class _FakeSdk:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.beta = self
        self.messages = self

    def create(self, **params):
        self.calls.append(params)
        return _FakeResponse(self.replies.pop(0))


def _anthropic_settings(**kw):
    return Settings(llm_provider="anthropic", anthropic_api_key="sk", anthropic_llm_model="claude-sonnet-5-5",
                    llm_price_input_per_m=2.0, llm_price_cached_per_m=0.2, llm_price_cache_write_per_m=2.5,
                    llm_price_output_per_m=10.0, **kw)


def test_create_client_picks_provider():
    from app.llm import AnthropicChatClient, create_client

    assert isinstance(create_client(_anthropic_settings()), AnthropicChatClient)
    assert isinstance(create_client(Settings(llm_provider="openai")), ChatClient)
    assert create_client(_anthropic_settings()).enabled and create_client(_anthropic_settings()).model == "claude-sonnet-5-5"


def test_anthropic_adapter_converts_messages_tools_and_usage():
    from app.llm import AnthropicChatClient

    thinking = {"type": "thinking", "thinking": "", "signature": "sig"}
    reply = {"stop_reason": "tool_use",
             "content": [thinking, {"type": "text", "text": "Measuring."},
                         {"type": "tool_use", "id": "tu1", "name": "measure", "input": {"word_ids": ["p1w1"]}}],
             "usage": {"input_tokens": 100, "cache_read_input_tokens": 900, "cache_creation_input_tokens": 50, "output_tokens": 40}}
    sdk = _FakeSdk([reply, {"stop_reason": "end_turn", "content": [{"type": "text", "text": "done"}], "usage": {"input_tokens": 10, "output_tokens": 5}}])
    client = AnthropicChatClient(_anthropic_settings(), sdk=sdk)
    tools = [{"type": "function", "function": {"name": "measure", "description": "d", "parameters": {"type": "object"}}}]
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": [{"type": "text", "text": "look"}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}}]},
    ]
    out = client.chat(messages, tools=tools)
    first = sdk.calls[0]
    assert first["system"] == "SYS" and first["cache_control"] == {"type": "ephemeral"}
    assert first["betas"] == ["server-side-fallback-2026-07-01"] and first["fallbacks"] == "default"
    assert first["tools"] == [{"name": "measure", "description": "d", "input_schema": {"type": "object"}}]
    assert first["messages"][0]["content"][1] == {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}}
    assert "temperature" not in first
    assert out["content"] == "Measuring." and out["tool_calls"][0]["function"]["name"] == "measure"

    messages += [out, {"role": "tool", "tool_call_id": "tu1", "content": "table"},
                 {"role": "tool", "tool_call_id": "tu2", "content": "Error: bad id"},
                 {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,WFla"}}]}]
    client.chat(messages, tools=tools)
    sent = sdk.calls[1]["messages"]
    assert sent[1] == {"role": "assistant", "content": reply["content"]}
    assert [b["type"] for b in sent[2]["content"]] == ["tool_result", "tool_result", "image"]
    assert sent[2]["content"][1]["is_error"] is True and "is_error" not in sent[2]["content"][0]

    usage = client.usage
    assert (usage.calls, usage.input_tokens, usage.cached_tokens, usage.cache_write_tokens, usage.output_tokens) == (2, 1060, 900, 50, 45)
    expected = (110 * 2.0 + 900 * 0.2 + 50 * 2.5 + 45 * 10.0) / 1_000_000
    assert client.usage_report(1)["cost_usd"] == round(expected, 5)


def test_anthropic_errors_become_llm_errors():
    from app.llm import AnthropicChatClient

    class Boom(_FakeSdk):
        def create(self, **params):
            raise RuntimeError("overloaded")

    with pytest.raises(LLMError):
        AnthropicChatClient(_anthropic_settings(anthropic_fallbacks=False), sdk=Boom([])).chat([{"role": "user", "content": "x"}])
