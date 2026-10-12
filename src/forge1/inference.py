"""Reference autoregressive generation with explicit, bounded compute budgets."""
from __future__ import annotations

from dataclasses import dataclass
import math
import time

import torch

MODES = {"fast": 1, "balanced": 2, "deep": 4}


@dataclass
class GenerationResult:
    token_ids: list[int]
    completion_ids: list[int]
    loops: int
    finish_reason: str
    seconds: float


def resolve_loops(mode: str, max_loops: int) -> int:
    if mode not in MODES:
        raise ValueError(f"Unknown thinking mode {mode!r}; choose {list(MODES)}")
    loops = MODES[mode]
    if loops > max_loops:
        raise ValueError("Requested compute mode exceeds the model's supported depth")
    return loops


@torch.inference_mode()
def generate(model, input_ids: list[int], *, mode: str = "balanced", loops: int | None = None,
             max_new_tokens: int = 128, temperature: float = 0.0, top_p: float = 1.0,
             seed: int = 42, stop_ids: list[int] | None = None,
             max_seconds: float | None = None) -> GenerationResult:
    """Correctness-first full-prefix execution, with no cross-depth KV cache reuse.

    Fixed per-request depth preserves the causal prefix computation. 'Deep' means
    more compute, not a guarantee of better answers. Context overflow fails early.
    """
    if not input_ids or max_new_tokens < 1:
        raise ValueError("A nonempty prompt and positive max_new_tokens are required")
    if not math.isfinite(temperature) or temperature < 0 or not 0 < top_p <= 1:
        raise ValueError("Invalid sampling parameters")
    if max_seconds is not None and (not math.isfinite(max_seconds) or max_seconds <= 0):
        raise ValueError("max_seconds must be positive and finite")
    if len(input_ids) + max_new_tokens > model.config.max_seq_len:
        raise ValueError("Prompt plus completion exceeds context; reduce length explicitly")
    if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= model.config.vocab_size for i in input_ids):
        raise ValueError("Prompt token outside model vocabulary")
    count = resolve_loops(mode, model.config.max_loops) if loops is None else loops
    model.config.executed_layers(count)
    device = next(model.parameters()).device
    rng = torch.Generator(device=device).manual_seed(seed)
    stops = set(stop_ids if stop_ids is not None else [model.config.eos_token_id])
    ids = torch.tensor([input_ids], dtype=torch.long, device=device)
    was_training = model.training
    model.eval()
    started = time.perf_counter()
    finish = "length"
    try:
        for _ in range(max_new_tokens):
            if max_seconds is not None and time.perf_counter() - started >= max_seconds:
                finish = "time_limit"
                break
            scores = model(ids, loops=count).logits[:, -1].float()
            scores[:, model.config.pad_token_id] = -torch.inf
            if temperature == 0:
                next_token = scores.argmax(dim=-1, keepdim=True)
            else:
                scores = scores / temperature
                sorted_scores, order = scores.sort(descending=True)
                cumulative = sorted_scores.softmax(-1).cumsum(-1)
                remove = cumulative > top_p
                remove[:, 1:] = remove[:, :-1].clone()
                remove[:, 0] = False
                sorted_scores.masked_fill_(remove, -torch.inf)
                probabilities = torch.zeros_like(scores).scatter(1, order, sorted_scores.softmax(-1))
                next_token = torch.multinomial(probabilities, 1, generator=rng)
            ids = torch.cat((ids, next_token), dim=1)
            if int(next_token.item()) in stops:
                finish = "stop"
                break
        all_ids = ids[0].tolist()
        return GenerationResult(all_ids, all_ids[len(input_ids):], count, finish, time.perf_counter() - started)
    finally:
        model.train(was_training)
