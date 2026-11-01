"""One test per transport behaviour, over a real socket.

MockTransport covers request shape; this covers httpx actually talking to a server,
including chunking and connection reuse.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pretext.client import Client
from pretext.models import APIError, Profile, Settings, Simulation

PAYLOAD = {
    "pretext": "x" * 120,
    "opening_message": "Hello, quick question about the ticket.",
    "escalation_path": [
        {
            "stage": 1,
            "channel": "email",
            "action": "Send the ticket stub.",
            "goal": "Open a thread",
        },
        {
            "stage": 2,
            "channel": "phone",
            "action": "Call about the ticket.",
            "goal": "Get a callback",
        },
    ],
    "red_flags": [
        {
            "title": "Odd domain",
            "why_it_matters": "Wrong sender domain.",
            "defender_action": "Check it",
        },
        {
            "title": "Rush",
            "why_it_matters": "Same day deadline.",
            "defender_action": "Verify elsewhere",
        },
    ],
    "difficulty": 2,
}


class Handler(BaseHTTPRequestHandler):
    failures = 0
    calls = 0

    def do_POST(self) -> None:
        type(self).calls += 1
        self.rfile.read(int(self.headers.get("content-length", 0) or 0))
        if type(self).failures > 0:
            type(self).failures -= 1
            self.send_response(503)
            self.send_header("retry-after", "0")
            self.end_headers()
            return
        body = json.dumps(
            {
                "choices": [{"message": {"content": json.dumps(PAYLOAD)}}],
                "usage": {"total_tokens": 7},
            }
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr("pretext.client.time.sleep", lambda _: None)
    Handler.failures = 0
    Handler.calls = 0
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    httpd.shutdown()
    httpd.server_close()


def settings(url: str, **over) -> Settings:
    base = {"base_url": url, "model": "m", "api_key": "k"}
    base.update(over)
    return Settings(**base)


def profile() -> Profile:
    return Profile(name="Ana Lima", role="Analyst", company="Cobalt", communication_style="Blunt")


def test_generates_over_a_socket(server):
    simulation = Client(settings(server)).generate(profile())
    assert isinstance(simulation, Simulation)
    assert Handler.calls == 1


def test_retries_a_503_over_a_socket(server):
    Handler.failures = 1
    simulation = Client(settings(server, retries=1)).generate(profile())
    assert simulation.difficulty == 2
    assert Handler.calls == 2


def test_usage_is_captured_over_a_socket(server):
    client = Client(settings(server))
    client.generate(profile())
    assert client.last_usage == {"total_tokens": 7}


def test_connection_refused_is_wrapped():
    client = Client(settings("http://127.0.0.1:9/v1", retries=0))
    with pytest.raises(APIError, match="connection failed"):
        client.generate(profile())
