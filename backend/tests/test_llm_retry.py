import json
import pytest
from app import llm


def test_retries_503_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky(url, payload, headers=None, timeout=90):
        calls["n"] += 1
        if calls["n"] < 3:
            raise llm.LLMError("HTTP 503: high demand")
        return {"ok": True}

    monkeypatch.setattr(llm, "_post_once", flaky)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert llm._post("u", {}) == {"ok": True} and calls["n"] == 3


def test_does_not_retry_bad_key(monkeypatch):
    calls = {"n": 0}

    def bad(url, payload, headers=None, timeout=90):
        calls["n"] += 1
        raise llm.LLMError("HTTP 400: API key not valid")

    monkeypatch.setattr(llm, "_post_once", bad)
    with pytest.raises(llm.LLMError):
        llm._post("u", {})
    assert calls["n"] == 1


def test_sends_custom_user_agent(monkeypatch):
    import io
    sent = {}

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        sent.update({k.lower(): v for k, v in req.header_items()})
        return Resp(b'{"ok": true}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    llm._post_once("http://x", {}, {"Authorization": "Bearer k"})
    assert sent["user-agent"] == "agentic-analyst/1.0" and sent["authorization"] == "Bearer k"


def test_salvages_plan_from_tool_use_failed(monkeypatch):
    plan = {"steps": [{"tool": "top_n", "args": {"column": "sales"}}]}
    body = json.dumps({"error": {"code": "tool_use_failed",
                                 "failed_generation": json.dumps({"name": "commentary", "arguments": plan})}})

    def rejected(url, payload, headers=None, timeout=90):
        err = llm.LLMError("HTTP 400: " + body[:60])
        err.body = body
        raise err

    monkeypatch.setattr(llm, "_post_once", rejected)
    data = llm._post_chat("u", {})
    assert json.loads(data["choices"][0]["message"]["content"]) == plan


def test_other_400_errors_are_not_salvaged(monkeypatch):
    def bad(url, payload, headers=None, timeout=90):
        err = llm.LLMError("HTTP 400: Incorrect API key")
        err.body = '{"error": {"message": "Incorrect API key"}}'
        raise err

    monkeypatch.setattr(llm, "_post_once", bad)
    with pytest.raises(llm.LLMError):
        llm._post_chat("u", {})


def test_salvages_direct_tool_call(monkeypatch):
    call = {"name": "make_chart", "arguments": {"kind": "bar", "x": "product", "y": "units"}}
    body = json.dumps({"error": {"code": "tool_use_failed", "failed_generation": json.dumps(call)}})

    def rejected(url, payload, headers=None, timeout=90):
        err = llm.LLMError("HTTP 400")
        err.body = body
        raise err

    monkeypatch.setattr(llm, "_post_once", rejected)
    steps = json.loads(llm._post_chat("u", {})["choices"][0]["message"]["content"])["steps"]
    assert steps == [{"tool": "make_chart", "args": call["arguments"]}]
