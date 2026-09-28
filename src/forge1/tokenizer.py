"""Tokenizers created from private data only; no remote model loading is supported."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Protocol


SPECIAL_TOKENS = (
    "<|pad|>", "<|bos|>", "<|eos|>", "<|system|>", "<|user|>",
    "<|assistant|>", "<|tool|>", "<|turn_end|>", "<|work|>",
    "<|answer|>", "<|check|>",
) + tuple(f"<|reserved_{i}|>" for i in range(11, 32))
SPECIAL_IDS = {token: index for index, token in enumerate(SPECIAL_TOKENS)}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class TokenizerProtocol(Protocol):
    vocab_size: int
    pad_id: int
    bos_id: int
    eos_id: int

    @property
    def fingerprint(self) -> str: ...

    def encode(self, text: str, add_bos: bool = False, add_eos: bool = False) -> list[int]: ...

    def decode(self, ids: Iterable[int], skip_special_tokens: bool = True) -> str: ...

    def save(self, path: str | Path) -> None: ...


class _TokenizerBase:
    pad_id = 0
    bos_id = 1
    eos_id = 2
    special_tokens = SPECIAL_IDS
    special_ids = SPECIAL_IDS

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self._payload()).encode("utf-8")).hexdigest()

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _payload(self) -> dict:
        raise NotImplementedError


class ByteTokenizer(_TokenizerBase):
    """Deterministic UTF-8 baseline: 32 reserved controls and 256 byte tokens.

    Literal control spellings in text are always ordinary bytes. This tokenizer is
    useful for tests and bootstrapping; train a fresh BPE before a production run.
    """

    vocab_size = 288

    def encode(self, text: str, add_bos: bool = False, add_eos: bool = False) -> list[int]:
        if not isinstance(text, str):
            raise TypeError("Tokenizer input must be a string")
        result = [byte + 32 for byte in text.encode("utf-8")]
        return ([self.bos_id] if add_bos else []) + result + ([self.eos_id] if add_eos else [])

    def decode(self, ids: Iterable[int], skip_special_tokens: bool = True) -> str:
        result: list[str] = []
        pending = bytearray()

        def flush() -> None:
            if pending:
                result.append(pending.decode("utf-8", errors="replace"))
                pending.clear()

        for token in ids:
            token = int(token)
            if token < 0 or token >= self.vocab_size:
                raise ValueError(f"Token id outside vocabulary: {token}")
            if token < 32:
                if not skip_special_tokens:
                    flush()
                    result.append(SPECIAL_TOKENS[token])
            else:
                pending.append(token - 32)
        flush()
        return "".join(result)

    def _payload(self) -> dict:
        return {"format": "forge1-tokenizer", "version": 1, "kind": "byte",
                "special_tokens": list(SPECIAL_TOKENS), "vocab_size": self.vocab_size}


class PrivateBPETokenizer(_TokenizerBase):
    """Byte-level BPE with preserved Unicode, isolated digits, and fixed controls."""

    def __init__(self, backend, training: dict | None = None):
        self.backend = backend
        self.training = training or {}
        self.backend.encode_special_tokens = True
        self.vocab_size = self.backend.get_vocab_size()
        for index, token in enumerate(SPECIAL_TOKENS):
            if self.backend.token_to_id(token) != index:
                raise ValueError("BPE special token ids do not match the FORGE-1 contract")

    def encode(self, text: str, add_bos: bool = False, add_eos: bool = False) -> list[int]:
        if not isinstance(text, str):
            raise TypeError("Tokenizer input must be a string")
        ids = self.backend.encode(text, add_special_tokens=False).ids
        # This second guard also covers tokenizer-library behavior changes. A
        # literal special token can never become a protocol boundary through data.
        if any(token < 32 for token in ids):
            ids = [token for char in text for token in self.backend.encode(char, add_special_tokens=False).ids]
        if any(token < 32 for token in ids):
            raise ValueError("Tokenizer interpreted ordinary data as a control token")
        return ([self.bos_id] if add_bos else []) + ids + ([self.eos_id] if add_eos else [])

    def decode(self, ids: Iterable[int], skip_special_tokens: bool = True) -> str:
        ids = [int(token) for token in ids]
        if any(token < 0 or token >= self.vocab_size for token in ids):
            raise ValueError("Token id outside vocabulary")
        if skip_special_tokens:
            ids = [token for token in ids if token >= 32]
            return self.backend.decode(ids, skip_special_tokens=False)
        chunks: list[str] = []
        pending: list[int] = []
        for token in ids:
            if token < 32:
                if pending:
                    chunks.append(self.backend.decode(pending, skip_special_tokens=False))
                    pending.clear()
                chunks.append(SPECIAL_TOKENS[token])
            else:
                pending.append(token)
        if pending:
            chunks.append(self.backend.decode(pending, skip_special_tokens=False))
        return "".join(chunks)

    def _payload(self) -> dict:
        return {"format": "forge1-tokenizer", "version": 1, "kind": "bpe",
                "special_tokens": list(SPECIAL_TOKENS), "vocab_size": self.vocab_size,
                "training": self.training, "backend": json.loads(self.backend.to_str())}


def load_tokenizer(path: str | Path) -> ByteTokenizer | PrivateBPETokenizer:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("format") != "forge1-tokenizer" or payload.get("version") != 1:
        raise ValueError("Unsupported tokenizer format/version")
    if payload.get("special_tokens") != list(SPECIAL_TOKENS):
        raise ValueError("Tokenizer special token contract differs")
    if payload.get("kind") == "byte":
        tokenizer = ByteTokenizer()
    elif payload.get("kind") == "bpe":
        from tokenizers import Tokenizer
        tokenizer = PrivateBPETokenizer(Tokenizer.from_str(_canonical(payload["backend"])), payload.get("training"))
    else:
        raise ValueError("Unsupported tokenizer kind")
    if payload.get("vocab_size") != tokenizer.vocab_size:
        raise ValueError("Tokenizer vocabulary size is inconsistent")
    return tokenizer


def train_bpe_tokenizer(manifest_path: str | Path, output_path: str | Path,
                        vocab_size: int = 49152, min_frequency: int = 2) -> PrivateBPETokenizer:
    """Train only on approved local sources explicitly assigned to the train split."""
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
    from .data import iter_training_texts, validate_manifest

    if vocab_size < 288:
        raise ValueError("vocab_size must reserve at least 32 controls and 256 bytes")
    if min_frequency < 1:
        raise ValueError("min_frequency must be positive")
    report = validate_manifest(manifest_path)
    if report["split_records"].get("train", 0) == 0:
        raise ValueError("Tokenizer training requires approved train-split records")
    backend = Tokenizer(models.BPE(unk_token=None))
    backend.pre_tokenizer = pre_tokenizers.Sequence([
        pre_tokenizers.Digits(individual_digits=True),
        pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=True),
    ])
    backend.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(vocab_size=vocab_size, min_frequency=min_frequency,
        special_tokens=list(SPECIAL_TOKENS), initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        show_progress=False)
    backend.train_from_iterator(iter_training_texts(manifest_path), trainer=trainer)
    # Reject concurrent source changes before publishing the tokenizer artifact.
    after = validate_manifest(manifest_path)
    if after["fingerprint"] != report["fingerprint"]:
        raise ValueError("Manifest changed during tokenizer training")
    tokenizer = PrivateBPETokenizer(backend, {"manifest_fingerprint": report["fingerprint"],
        "requested_vocab_size": vocab_size, "min_frequency": min_frequency, "split": "train"})
    tokenizer.save(output_path)
    return tokenizer
