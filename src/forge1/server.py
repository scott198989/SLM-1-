"""Local chat-completions schema adapter, deliberately small and non-streaming.

This is a development endpoint, not a public multi-tenant inference server.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
import uuid

import torch

from .checkpoint import model_from_checkpoint
from .data import encode_chat
from .inference import generate
from .tokenizer import load_tokenizer

DEFAULT_SYSTEM = (
    "You are FORGE, a friendly engineering collaborator specializing in mechatronics, "
    "engineering mathematics, and materials science. State the assumptions that matter, "
    "check units and constraints, and explain results clearly and warmly. Ask for missing "
    "engineering inputs. Say when a claim has not been verified. Politely redirect unrelated requests. "
    "Do not claim you ran tools, simulations, or measurements unless their results are supplied."
)


def completion(model, tokenizer, request: dict) -> dict:
    if not isinstance(request, dict):
        raise ValueError("Request must be a JSON object")
    supported = {"model", "messages", "stream", "temperature", "top_p", "max_tokens", "seed", "thinking_mode"}
    unknown = set(request) - supported
    if unknown:
        raise ValueError(f"Unsupported request fields: {sorted(unknown)}")
    if request.get("model", "forge-1b") != "forge-1b":
        raise ValueError("Only model='forge-1b' is available")
    if request.get("stream", False):
        raise ValueError("Streaming is not implemented; use stream=false")
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a nonempty array")
    if not any(isinstance(message, dict) and message.get("role") == "system" for message in messages):
        messages = [{"role": "system", "content": DEFAULT_SYSTEM}, *messages]
    ids = encode_chat(messages, tokenizer, add_assistant_prompt=True)
    max_tokens = request.get("max_tokens", 128)
    seed = request.get("seed", 42)
    if type(max_tokens) is not int or max_tokens < 1 or type(seed) is not int:
        raise ValueError("max_tokens must be positive integer and seed integer")
    result = generate(model, ids, mode=request.get("thinking_mode", "balanced"), max_new_tokens=max_tokens,
                      temperature=request.get("temperature", 0.0), top_p=request.get("top_p", 1.0),
                      seed=seed, max_seconds=120,
                      stop_ids=[tokenizer.eos_id, tokenizer.special_ids["<|turn_end|>"]])
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex, "object": "chat.completion", "created": int(time.time()),
        "model": "forge-1b", "choices": [{"index": 0, "message": {"role": "assistant", "content": tokenizer.decode(result.completion_ids)},
                                           "finish_reason": result.finish_reason}],
        "usage": {"prompt_tokens": len(ids), "completion_tokens": len(result.completion_ids), "total_tokens": len(result.token_ids)},
        "forge": {"loops": result.loops, "seconds": result.seconds,
                  "scope_enforcement": "learned behavior requires validated domain training; prompt alone is not enforcement"},
    }


def serve(checkpoint: str, tokenizer_path: str, *, device: str = "cpu", port: int = 8000):
    if not 1024 <= port <= 65535:
        raise ValueError("Choose an unprivileged TCP port (1024..65535)")
    model, payload = model_from_checkpoint(checkpoint, device=device,
                                           dtype=torch.bfloat16 if device == "cuda" else None)
    tokenizer = load_tokenizer(tokenizer_path)
    if tokenizer.fingerprint != payload["tokenizer_fingerprint"]:
        raise ValueError("Server tokenizer differs from checkpoint")
    # Drop the training optimizer from CPU memory before serving.
    checkpoint_info = {key: payload.get(key) for key in ("stage", "step", "is_fixture")}
    del payload

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10.0)

        def _respond(self, status, value):
            data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._respond(200, {"status": "ready", "checkpoint": checkpoint_info,
                                    "capability": "training status does not establish engineering competence"})
            elif self.path == "/v1/models":
                self._respond(200, {"object": "list", "data": [{"id": "forge-1b", "object": "model", "owned_by": "local"}]})
            else:
                self._respond(404, {"error": {"message": "Unknown endpoint"}})

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self._respond(404, {"error": {"message": "Unknown endpoint"}})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1_048_576:
                    raise ValueError("JSON body must be between 1 byte and 1 MiB")
                request = json.loads(self.rfile.read(length))
                self._respond(200, completion(model, tokenizer, request))
            except TimeoutError:
                self._respond(408, {"error": {"message": "Request body timed out", "type": "request_timeout"}})
            except (ValueError, TypeError, KeyError) as error:
                self._respond(400, {"error": {"message": str(error), "type": "invalid_request_error"}})
            except RuntimeError as error:
                self._respond(500, {"error": {"message": str(error), "type": "inference_error"}})

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 10
    print(f"FORGE local development server: http://127.0.0.1:{port}; checkpoint={checkpoint_info}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
