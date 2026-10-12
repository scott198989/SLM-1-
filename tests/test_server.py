"""Actual local HTTP development endpoint tests using a tiny random checkpoint."""

import http.client
from http.server import HTTPServer
import json
import socket
import threading
from unittest.mock import patch

import pytest
import torch

from forge1.checkpoint import FORMAT_VERSION, atomic_torch_save, load_checkpoint
from forge1.config import ModelConfig
from forge1.inference import GenerationResult
from forge1.model import ForgeModel
from forge1.server import completion, serve
from forge1.tokenizer import ByteTokenizer


@pytest.fixture
def tiny_policy():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    torch.manual_seed(301)
    config = ModelConfig(vocab_size=288, d_model=16, n_heads=2, n_kv_heads=1,
        intermediate_size=32, stem_layers=0, core_layers=1, speaker_layers=0,
        ledger_enabled=True, ledger_rank=4, max_seq_len=1024, default_loops=1, max_loops=4)
    yield ForgeModel(config), ByteTokenizer()
    torch.set_num_threads(previous)


def request(body=None, **kwargs):
    return {"model": "forge-1b", "messages": [{"role": "system", "content": "Be precise."},
            {"role": "user", "content": "What is 1+1?"}], "max_tokens": 1,
            "thinking_mode": "fast", **(body or {}), **kwargs}


def test_real_completion_shape_usage_and_honest_scope(tiny_policy):
    model, tokenizer = tiny_policy
    result = completion(model, tokenizer, request())
    assert result["object"] == "chat.completion"
    assert result["choices"][0]["message"]["role"] == "assistant"
    assert isinstance(result["choices"][0]["message"]["content"], str)
    assert result["usage"]["completion_tokens"] == 1
    assert result["usage"]["total_tokens"] == result["usage"]["prompt_tokens"] + 1
    assert result["forge"]["loops"] == 1
    assert "prompt alone is not enforcement" in result["forge"]["scope_enforcement"]


def test_default_system_and_generation_time_bound_are_explicit(tiny_policy):
    model, tokenizer = tiny_policy
    result = GenerationResult([1, 50], [50], 2, "time_limit", 0.01)
    with patch("forge1.server.generate", return_value=result) as generate:
        response = completion(model, tokenizer, {"messages": [{"role": "user", "content": "Torque?"}]})
    prompt = tokenizer.decode(generate.call_args.args[1])
    assert "friendly engineering collaborator" in prompt
    assert "Do not claim you ran tools" in prompt
    assert generate.call_args.kwargs["max_seconds"] == 120
    assert response["choices"][0]["finish_reason"] == "time_limit"


@pytest.mark.parametrize("invalid", [[], {}, {"model": "another-model"}, {"stream": True},
    {"max_tokens": True}, {"max_tokens": 0}, {"max_tokens": 100000}, {"seed": 1.5},
    {"messages": []}, {"messages": [{"role": "user", "content": 3}]},
    {"messages": [{"role": "tool", "content": "unmatched", "tool_call_id": "x"}]},
    {"temperature": float("nan")}, {"top_p": 0}, {"thinking_mode": "unbounded"}, {"unknown": 1}])
def test_invalid_completion_requests_fail_explicitly(tiny_policy, invalid):
    model, tokenizer = tiny_policy
    value = invalid if isinstance(invalid, list) or invalid == {} else request(invalid)
    with pytest.raises((ValueError, TypeError, KeyError)):
        completion(model, tokenizer, value)


@pytest.fixture
def local_server(tmp_path, tiny_policy):
    model, tokenizer = tiny_policy
    checkpoint, tokenizer_path = tmp_path / "tiny.pt", tmp_path / "tokenizer.json"
    tokenizer.save(tokenizer_path)
    atomic_torch_save({"format_version": FORMAT_VERSION, "model_config": model.config.to_dict(),
        "model": model.state_dict(), "tokenizer_fingerprint": tokenizer.fingerprint,
        "step": 0, "stage": "random_test_fixture", "is_fixture": True}, checkpoint)
    holder = {}
    ready = threading.Event()
    failures = []

    def server_factory(address, handler):
        assert address[0] == "127.0.0.1"
        instance = HTTPServer(("127.0.0.1", 0), handler)
        holder["server"] = instance
        ready.set()
        return instance

    def run():
        try:
            serve(str(checkpoint), str(tokenizer_path), port=8123)
        except BaseException as error:
            failures.append(error)
            ready.set()

    with patch("forge1.server.HTTPServer", side_effect=server_factory):
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        assert ready.wait(3), "Server failed to initialize"
        assert not failures
        server = holder["server"]
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=3)
            assert not thread.is_alive(), "Local server failed to stop"
            assert not failures


def fetch(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_live_http_health_models_unknown_and_completion(local_server):
    status, health = fetch(local_server, "GET", "/health")
    assert status == 200 and health["status"] == "ready"
    assert health["checkpoint"] == {"stage": "random_test_fixture", "step": 0, "is_fixture": True}
    assert "does not establish engineering competence" in health["capability"]
    status, models = fetch(local_server, "GET", "/v1/models")
    assert status == 200 and models["data"][0]["id"] == "forge-1b"
    assert fetch(local_server, "GET", "/missing")[0] == 404
    status, answer = fetch(local_server, "POST", "/v1/chat/completions", json.dumps(request()), {"Content-Type": "application/json"})
    assert status == 200 and answer["usage"]["completion_tokens"] == 1
    assert fetch(local_server, "POST", "/missing", "{}")[0] == 404


@pytest.mark.parametrize("body,headers", [("{broken", {}), ("[]", {}), ("", {}),
    ("{}", {"Content-Length": "1048577"}), ("{}", {"Content-Length": "invalid"}),
    (json.dumps(request(temperature="warm")), {}), (json.dumps(request(stream=True)), {})])
def test_live_http_invalid_json_and_request_limits_return_400(local_server, body, headers):
    status, response = fetch(local_server, "POST", "/v1/chat/completions", body, headers)
    assert status == 400
    assert response["error"]["type"] == "invalid_request_error"
    # The same process remains responsive after malformed input.
    assert fetch(local_server, "GET", "/health")[0] == 200


def test_live_http_generation_failure_returns_500_then_recovers(local_server):
    with patch("forge1.server.generate", side_effect=RuntimeError("Synthetic inference failure")):
        status, result = fetch(local_server, "POST", "/v1/chat/completions", json.dumps(request()))
    assert status == 500 and result["error"]["type"] == "inference_error"
    assert fetch(local_server, "GET", "/health")[0] == 200


def test_request_connection_has_a_real_read_timeout(local_server):
    # HTTPServer.timeout does not apply to serve_forever's blocking body read.
    # Inspect the accepted socket through the actual handler path, without
    # holding up tests for the production timeout interval.
    observed = []
    original = local_server.RequestHandlerClass.do_GET

    def observe(handler):
        observed.append(handler.connection.gettimeout())
        return original(handler)

    with patch.object(local_server.RequestHandlerClass, "do_GET", observe):
        assert fetch(local_server, "GET", "/health")[0] == 200
    assert observed and observed[0] is not None and 0 < observed[0] <= 120


def test_live_http_stalled_body_returns_408_and_server_recovers(local_server):
    original = local_server.RequestHandlerClass.setup

    def fast_timeout(handler):
        original(handler)
        handler.connection.settimeout(0.05)

    with patch.object(local_server.RequestHandlerClass, "setup", fast_timeout):
        with socket.create_connection(("127.0.0.1", local_server.server_port), timeout=1) as connection:
            connection.sendall(b"POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Length: 99\r\n\r\n{")
            response = http.client.HTTPResponse(connection)
            response.begin()
            payload = json.loads(response.read())
            assert response.status == 408
            assert payload["error"]["type"] == "request_timeout"
    assert fetch(local_server, "GET", "/health")[0] == 200


def test_serve_rejects_privileged_port(tiny_policy):
    with pytest.raises(ValueError, match="unprivileged"):
        serve("unused.pt", "unused.json", port=80)


def test_malformed_checkpoint_payload_has_explicit_format_error(tmp_path):
    path = tmp_path / "malformed.pt"
    torch.save([], path)
    with pytest.raises(ValueError, match="checkpoint format"):
        load_checkpoint(path)
