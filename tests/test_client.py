from __future__ import annotations

import json

import httpx
import pytest

from pretext.client import Client, extract_json
from pretext.models import APIError, Settings, Simulation
from pretext.prompt import build_payload_messages

PROFILE = {
    "name": "Dana Iyer",
    "role": "Senior Payroll Analyst",
    "company": "Northwind Logistics",
    "communication_style": "Brisk and formal",
}

STEPS = [
    {"stage": 1, "channel": "email", "action": "Send a fake invoice query.", "goal": "Open a thread"},
    {"stage": 2, "channel": "phone", "action": "Call to confirm the invoice.", "goal": "Get a callback"},
]
FLAGS = [
    {"title": "Odd domain", "why_it_matters": "Vendor mail came from elsewhere.", "defender_action": "Check the domain"},
    {"title": "Urgency", "why_it_matters": "Deadline is same day.", "defender_action": "Verify out of band"},
]

PAYLOAD = {
    "pretext": "x" * 100,
    "opening_message": "Hi Dana, quick one on the invoice.",
    "escalation_path": STEPS,
    "red_flags": FLAGS,
    "difficulty": 3,
}


def settings(**over):
    base = {"base_url": "http://api.test/v1", "model": "test-model", "api_key": "sk-x", "retries": 2}
    base.update(over)
    return Settings(**base)


def chat_response(content: str, status: int = 200, **headers):
    return httpx.Response(
        status,
        json={"choices": [{"message": {"role": "assistant", "content": content}}]},
        headers=headers,
    )


def client_with(handler, **over):
    return Client(settings(**over), transport=httpx.MockTransport(handler))


def test_extract_plain_json():
    assert extract_json(json.dumps(PAYLOAD))["difficulty"] == 3


def test_extract_fenced_json():
    assert extract_json("```json\n" + json.dumps(PAYLOAD) + "\n```")["difficulty"] == 3


def test_extract_prefixed_prose():
    assert extract_json("Sure! Here you go:\n" + json.dumps(PAYLOAD) + "\nDone.")["difficulty"] == 3


def test_extract_garbage():
    with pytest.raises(APIError, match="no JSON object"):
        extract_json("no json here")


def test_extract_malformed():
    with pytest.raises(APIError, match="malformed JSON"):
        extract_json('{"a": 1,}')


def test_extract_requires_object():
    with pytest.raises(APIError, match="JSON object"):
        extract_json("[1, 2]")


def test_generate_success_sends_expected_request():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return chat_response(json.dumps(PAYLOAD))

    from pretext.models import Profile

    sim = client_with(handler).generate(Profile(**PROFILE), channel="email", extra="keep it short")
    assert isinstance(sim, Simulation)
    assert seen["url"] == "http://api.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-x"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["model"] == "test-model"
    assert "email channel" in seen["body"]["messages"][1]["content"]
    assert "keep it short" in seen["body"]["messages"][1]["content"]


def test_generate_handles_list_content():
    def handler(request):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": [{"type": "text", "text": json.dumps(PAYLOAD)}]}}]},
        )

    from pretext.models import Profile

    assert client_with(handler).generate(Profile(**PROFILE)).difficulty == 3


def test_retry_then_success(monkeypatch):
    monkeypatch.setattr("pretext.client.time.sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, headers={"retry-after": "0"})
        return chat_response(json.dumps(PAYLOAD))

    from pretext.models import Profile

    assert client_with(handler).generate(Profile(**PROFILE)).difficulty == 3
    assert calls["n"] == 2


def test_retries_exhausted(monkeypatch):
    monkeypatch.setattr("pretext.client.time.sleep", lambda _: None)

    def handler(request):
        return httpx.Response(500)

    from pretext.models import Profile

    with pytest.raises(APIError, match="HTTP 500"):
        client_with(handler, retries=1).generate(Profile(**PROFILE))


def test_no_retry_on_400():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    from pretext.models import Profile

    with pytest.raises(APIError, match="bad key"):
        client_with(handler).generate(Profile(**PROFILE))
    assert calls["n"] == 1


def test_timeout_then_failure(monkeypatch):
    monkeypatch.setattr("pretext.client.time.sleep", lambda _: None)

    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    from pretext.models import Profile

    with pytest.raises(APIError, match="timed out"):
        client_with(handler, retries=0).generate(Profile(**PROFILE))


def test_schema_violation_surfaces():
    def handler(request):
        return chat_response(json.dumps({**PAYLOAD, "escalation_path": []}))

    from pretext.models import Profile

    with pytest.raises(APIError, match="failed validation"):
        client_with(handler).generate(Profile(**PROFILE))


def test_empty_content():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "  "}}]})

    from pretext.models import Profile

    with pytest.raises(APIError, match="empty content"):
        client_with(handler).generate(Profile(**PROFILE))


def test_payload_prompt_includes_profile_details():
    from pretext.models import Profile

    messages = build_payload_messages(Profile(**PROFILE))
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "Northwind Logistics" in messages[1]["content"]


def test_usage_captured():
    def handler(request):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(PAYLOAD)}}],
                  "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        )

    from pretext.models import Profile

    client = client_with(handler)
    client.generate(Profile(**PROFILE))
    assert client.last_usage["total_tokens"] == 15


def test_content_of_rejects_bad_shapes():
    from pretext.client import _content_of

    for body in ({}, {"choices": []}, {"choices": [{}]}, {"choices": [{"message": {}}]}, {"choices": "x"}):
        with pytest.raises(APIError):
            _content_of(body)


def test_backoff_prefers_retry_after():
    from pretext.client import _backoff

    assert _backoff(1, "2") == 2.0
    assert _backoff(3, "999") == 30.0
    assert 0.3 < _backoff(1, "nonsense") <= 0.65


def test_decode_rejects_non_json():
    with pytest.raises(APIError, match="non-JSON"):
        client_with(lambda r: httpx.Response(200, text="<html>")).generate(_profile())


def test_decode_rejects_non_object():
    with pytest.raises(APIError, match="non-object"):
        client_with(lambda r: httpx.Response(200, json=[1, 2])).generate(_profile())


def test_error_text_shapes():
    def mk(**kwargs):
        return httpx.Response(400, **kwargs)

    from pretext.client import _error_text

    assert _error_text(mk(json={"error": {"message": "boom"}})) == "boom"
    assert _error_text(mk(json={"error": "flat"})) == "flat"
    assert _error_text(mk(json={"message": "hello"})) == "hello"
    assert _error_text(mk(text="raw text")) == "raw text"
    assert _error_text(mk()) == "<empty body>"


def test_seed_sent_when_set():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return chat_response(json.dumps(PAYLOAD))

    client_with(handler, seed=7).generate(_profile())
    assert seen["seed"] == 7


def test_seed_omitted_by_default():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return chat_response(json.dumps(PAYLOAD))

    client_with(handler).generate(_profile())
    assert "seed" not in seen


def _profile():
    from pretext.models import Profile

    return Profile(**PROFILE)


def test_extract_json_survives_junk():
    import random
    import string

    rng = random.Random(7)
    for _ in range(300):
        text = "".join(rng.choice(string.printable) for _ in range(rng.randint(0, 120)))
        try:
            result = extract_json(text)
        except APIError:
            continue
        assert isinstance(result, dict)


def test_extract_json_fenced_with_prose():
    fenced = "Here you go:\n```json\n" + json.dumps(PAYLOAD) + "\n```\nEnjoy."
    assert extract_json(fenced)["difficulty"] == 3


def test_extract_json_deep_nesting_still_parses():
    nested = json.dumps({**PAYLOAD, "objective": "{" * 3 + "x" + "}" * 3})
    assert extract_json(nested)["objective"].startswith("{")


def test_timeout_then_success(monkeypatch):
    monkeypatch.setattr("pretext.client.time.sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return chat_response(json.dumps(PAYLOAD))

    assert client_with(handler, retries=1).generate(_profile()).difficulty == 3


def test_connect_error_then_success(monkeypatch):
    monkeypatch.setattr("pretext.client.time.sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("refused", request=request)
        return chat_response(json.dumps(PAYLOAD))

    assert client_with(handler, retries=1).generate(_profile()).difficulty == 3


def test_error_text_non_object_body():
    from pretext.client import _error_text

    assert _error_text(httpx.Response(400, json=[1, 2])) == "[1, 2]"


def test_connect_error_exhausted(monkeypatch):
    monkeypatch.setattr("pretext.client.time.sleep", lambda _: None)

    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(APIError, match="connection failed"):
        client_with(handler, retries=1).generate(_profile())


def test_list_models_parses_ids():
    def handler(request):
        assert request.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}, {}]})

    assert client_with(handler).list_models() == ["a", "b"]


def test_list_models_404_means_unsupported():
    assert client_with(lambda r: httpx.Response(404, json={})).list_models() == []


def test_list_models_connect_failure(monkeypatch):
    monkeypatch.setattr("pretext.client.time.sleep", lambda _: None)

    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(APIError, match="model list unreachable"):
        client_with(handler).list_models()


def test_ping_json_returns_content():
    def handler(request):
        seen = json.loads(request.content)
        assert seen["response_format"] == {"type": "json_object"}
        return chat_response('{"ok": true}')

    assert client_with(handler).ping_json() == '{"ok": true}'
