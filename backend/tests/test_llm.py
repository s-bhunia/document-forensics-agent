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
