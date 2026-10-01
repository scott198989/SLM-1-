"""Use pinned real tokenizer/template; supervise only assistant content and end."""

import hashlib, json, re
from pathlib import Path
from jinja2.sandbox import ImmutableSandboxedEnvironment
from tokenizers import Tokenizer

SEGMENTS = re.compile(r"<\|im_start\|>(system|user|assistant)\n(.*?)<\|im_end\|>", re.S)


class QwenFormatter:
    def __init__(self, assets):
        assets = Path(assets)
        manifest = json.loads((assets / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["assets"]:
            if (
                hashlib.sha256((assets / item["path"]).read_bytes()).hexdigest()
                != item["sha256"]
            ):
                raise ValueError("tokenizer_asset_hash_mismatch")
        self.manifest = manifest
        self.tokenizer = Tokenizer.from_file(str(assets / "tokenizer.json"))
        config = json.loads(
            (assets / "tokenizer_config.json").read_text(encoding="utf-8")
        )
        environment = ImmutableSandboxedEnvironment(
            trim_blocks=True, lstrip_blocks=True
        )
        self.template = environment.from_string(config["chat_template"])
        self.end = self.tokenizer.token_to_id("<|im_end|>")
        self.base_eos = json.loads(
            (assets / "config.json").read_text(encoding="utf-8")
        )["eos_token_id"]
        if self.end is None or self.end == self.base_eos:
            raise ValueError("unexpected_eos_contract")

    def encode(self, messages, max_length=2048):
        if (
            not isinstance(messages, list)
            or not messages
            or type(max_length) is not int
            or max_length < 1
        ):
            raise ValueError("invalid_format_input")
        expected = "user"
        for i, m in enumerate(messages):
            if (
                set(m) != {"role", "content"}
                or not isinstance(m["content"], str)
                or not m["content"].strip()
            ):
                raise ValueError("invalid_message")
            role = m["role"]
            if role == "system" and i == 0:
                pass
            elif role != expected:
                raise ValueError("invalid_turn_order")
            else:
                expected = "assistant" if expected == "user" else "user"
            if (
                "<|" in m["content"]
                or "<think>" in m["content"]
                or "</think>" in m["content"]
            ):
                raise ValueError("embedded_template_control_requires_review")
        if messages[-1]["role"] != "assistant":
            raise ValueError("missing_answer")
        rendered = self.template.render(
            messages=messages,
            tools=None,
            add_generation_prompt=False,
            enable_thinking=False,
        )
        segments = list(SEGMENTS.finditer(rendered))
        if len(segments) != len(messages):
            raise ValueError("rendered_segment_count_mismatch")
        spans = [(m.start(2), m.end()) for m in segments if m[1] == "assistant"]
        encoding = self.tokenizer.encode(rendered, add_special_tokens=False)
        labels = []
        for token, (start, end) in zip(encoding.ids, encoding.offsets):
            overlaps = [span for span in spans if start < span[1] and end > span[0]]
            if overlaps and not any(start >= a and end <= b for a, b in overlaps):
                raise ValueError("token_crosses_loss_boundary")
            labels.append(token if overlaps else -100)
        if not any(x != -100 for x in labels):
            raise ValueError("empty_assistant_target")
        for segment in segments:
            if segment[1] == "assistant":
                selected = [
                    i
                    for i, (start, end) in enumerate(encoding.offsets)
                    if start >= segment.start(2)
                    and end <= segment.end()
                    and end > start
                ]
                if not selected or labels[selected[-1]] != self.end:
                    raise ValueError("assistant_end_not_supervised")
        return {
            "input_ids": encoding.ids,
            "attention_mask": [1] * len(labels),
            "labels": labels,
            "tokens": len(labels),
            "assistant_tokens": sum(x != -100 for x in labels),
            "over_context": len(labels) > max_length,
            "render_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        }
