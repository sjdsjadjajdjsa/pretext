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
