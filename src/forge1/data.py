"""Auditable local-data intake and document-isolated, memory-mapped datasets.

Every source must declare its rights and immutable hash. Preparation never
downloads a corpus, deduplicates silently, truncates a supervised example, or
packs unrelated documents into one attention context.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Iterator

import numpy as np

from .tokenizer import SPECIAL_IDS, TokenizerProtocol, load_tokenizer

STAGES = {"pretrain", "sft", "preference", "verifier", "rl"}
SPLITS = {"train", "validation", "test"}
DOMAINS = {"mechatronics", "mathematics", "materials_science", "engineering_conversation", "general_academics"}
IGNORE_INDEX = -100


class DataValidationError(ValueError):
    """Actionable source, schema, leakage, or preparation failure."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(f"{field} must be a non-empty string")
    return value


def _read_manifest(path: str | Path) -> tuple[Path, dict]:
    path = Path(path).resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DataValidationError(f"Cannot read manifest {path}: {error}") from error
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise DataValidationError("Manifest must be an object with version=1")
    if not isinstance(payload.get("sources"), list) or not payload["sources"]:
        raise DataValidationError("Manifest sources must be a non-empty list")
    if "is_fixture" in payload and not isinstance(payload["is_fixture"], bool):
        raise DataValidationError("Manifest is_fixture must be a boolean")
    return path, payload


def _source_path(manifest: Path, source: dict) -> Path:
    value = _nonempty(source.get("path"), "source.path")
    if "://" in value:
        raise DataValidationError("Sources must be local files; URLs are not accepted")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else manifest.parent / path).resolve()


def _iter_records(path: Path) -> Iterator[tuple[int, dict]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise DataValidationError(f"{path}:{line_number}: empty JSONL line; remove it explicitly")
            try:
                record = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Non-finite JSON {value}")))
            except ValueError as error:
                raise DataValidationError(f"{path}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(record, dict):
                raise DataValidationError(f"{path}:{line_number}: record must be an object")
            yield line_number, record


def validate_messages(messages: object, *, require_answer: bool = False) -> list[dict]:
    if not isinstance(messages, list) or not messages:
        raise DataValidationError("messages must be a non-empty list")
    seen_user = False
    pending_tools: set[str] = set()
    known_tools: set[str] = set()
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise DataValidationError(f"messages[{index}] must be an object")
        role = message.get("role")
        unknown = set(message) - {"role", "content", "name", "tool_call_id", "tool_calls"}
        if unknown:
            raise DataValidationError(f"Unknown message fields would be discarded: {sorted(unknown)}")
        if role not in {"system", "user", "assistant", "tool"}:
            raise DataValidationError(f"Unsupported message role {role!r}")
        if role == "system" and index != 0:
            raise DataValidationError("system message is allowed only at the start")
        if role == "user":
            seen_user = True
        if role in {"assistant", "tool"} and not seen_user:
            raise DataValidationError("assistant/tool message requires a preceding user message")
        content = message.get("content")
        if not isinstance(content, str):
            raise DataValidationError("Every message content must be a string")
        tool_calls = message.get("tool_calls", [])
        if not isinstance(tool_calls, list) or (tool_calls and role != "assistant"):
            raise DataValidationError("tool_calls must be a list on an assistant message")
        if not content.strip() and not tool_calls:
            raise DataValidationError("Empty message content requires assistant tool_calls")
        if pending_tools and role != "tool":
            raise DataValidationError("All assistant tool calls need responses before the next message")
        for call in tool_calls:
            if not isinstance(call, dict):
                raise DataValidationError("Each tool call must be an object")
            call_id = _nonempty(call.get("id"), "tool_call.id")
            _nonempty(call.get("name"), "tool_call.name")
            if not isinstance(call.get("arguments"), dict):
                raise DataValidationError("tool_call.arguments must be an object")
            if call_id in known_tools:
                raise DataValidationError(f"Duplicate tool call id: {call_id}")
            known_tools.add(call_id)
            pending_tools.add(call_id)
        if role == "tool":
            call_id = _nonempty(message.get("tool_call_id"), "tool.tool_call_id")
            if call_id not in pending_tools:
                raise DataValidationError("Tool result does not match a pending assistant call")
            pending_tools.remove(call_id)
        elif "tool_call_id" in message:
            raise DataValidationError("tool_call_id is allowed only on tool messages")
        if "name" in message:
            _nonempty(message["name"], "message.name")
    if pending_tools:
        raise DataValidationError("Conversation has unresolved assistant tool calls")
    if not seen_user:
        raise DataValidationError("Conversation requires a user message")
    if require_answer and messages[-1]["role"] != "assistant":
        raise DataValidationError("Supervised conversation must end with an assistant answer")
    return messages


def serialize_messages(messages: list[dict], tokenizer: TokenizerProtocol,
                       add_assistant_prompt: bool = False) -> tuple[list[int], list[bool]]:
    """Serialize the sole shared chat protocol; return tokens and assistant targets.

    Text is always encoded literally. Only this function inserts role controls.
    Assistant tool calls are supervised as deterministic JSON alongside content.
    """
    validate_messages(messages)
    ids = [tokenizer.bos_id]
    targets = [False]
    for message in messages:
        role = message["role"]
        ids.append(SPECIAL_IDS[f"<|{role}|>"])
        targets.append(False)
        header = {key: message[key] for key in ("name", "tool_call_id") if key in message}
        if header:
            encoded = tokenizer.encode(_canonical(header).decode("utf-8") + "\n")
            ids.extend(encoded)
            targets.extend([role == "assistant"] * len(encoded))
        content = message["content"]
        if message.get("tool_calls"):
            content += "\n" + _canonical({"tool_calls": message["tool_calls"]}).decode("utf-8")
        encoded = tokenizer.encode(content)
        ids.extend(encoded)
        targets.extend([role == "assistant"] * len(encoded))
        ids.append(SPECIAL_IDS["<|turn_end|>"])
        targets.append(role == "assistant")
    if add_assistant_prompt:
        ids.append(SPECIAL_IDS["<|assistant|>"])
        targets.append(False)
    return ids, targets


def encode_chat(messages: list[dict], tokenizer: TokenizerProtocol,
                add_assistant_prompt: bool = True) -> list[int]:
    """Return prompt tokens using exactly the training serialization."""
    return serialize_messages(messages, tokenizer, add_assistant_prompt)[0]


def _validate_auxiliary(record: dict) -> None:
    for name, length in (("constraint_labels", 4), ("si_dimensions", 7)):
        if name not in record:
            continue
        values = record[name]
        if not isinstance(values, list) or len(values) != length:
            raise DataValidationError(f"{name} must have length {length}")
        for value in values:
            if value is None:
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise DataValidationError(f"{name} values must be finite numbers or null")
            if name == "constraint_labels" and value not in {-1, 0, 1}:
                raise DataValidationError("constraint_labels values must be 0, 1, -1, or null")
    if "domain_label" in record and (type(record["domain_label"]) is not int or record["domain_label"] not in {-1, 0, 1, 2}):
        raise DataValidationError("domain_label must be -1, 0, 1, or 2")
    if "verifier_label" in record:
        value = record["verifier_label"]
        if value is not None and (type(value) not in {int, float} or value not in {-1, 0, 1}):
            raise DataValidationError("verifier_label must be 0, 1, -1, or null")


def _validate_record(record: dict, kind: str) -> None:
    _nonempty(record.get("id"), "record.id")
    accepted = {"id", "document_family"} | {
        "pretrain": {"text"},
        "sft": {"messages", "constraint_labels", "si_dimensions", "domain_label", "verifier_label"},
        "verifier": {"messages", "constraint_labels", "si_dimensions", "domain_label", "verifier_label"},
        "preference": {"prompt", "chosen", "rejected"}, "rl": {"prompt", "task"}}[kind]
    unknown = set(record) - accepted
    if unknown:
        raise DataValidationError(f"Unknown record fields would be discarded: {sorted(unknown)}")
    if kind == "pretrain":
        _nonempty(record.get("text"), "record.text")
    elif kind in {"sft", "verifier"}:
        validate_messages(record.get("messages"), require_answer=True)
        _validate_auxiliary(record)
        has_aux_target = (any(value in {0, 1} for value in record.get("constraint_labels", []))
            or any(value is not None for value in record.get("si_dimensions", []))
            or record.get("domain_label", -1) >= 0
            or record.get("verifier_label") in {0, 1})
        if kind == "verifier" and not has_aux_target:
            raise DataValidationError("Verifier record requires at least one observed auxiliary target")
    elif kind == "preference":
        validate_messages(record.get("prompt"))
        if record["prompt"][-1]["role"] not in {"user", "tool"}:
            raise DataValidationError("Preference prompt must end with user or tool")
        chosen = _nonempty(record.get("chosen"), "record.chosen")
        rejected = _nonempty(record.get("rejected"), "record.rejected")
        if chosen == rejected:
            raise DataValidationError("Preference chosen and rejected responses must differ")
    elif kind == "rl":
        validate_messages(record.get("prompt"))
        if record["prompt"][-1]["role"] not in {"user", "tool"}:
            raise DataValidationError("RL prompt must end with user or tool")
        if not isinstance(record.get("task"), dict) or not record["task"]:
            raise DataValidationError("RL record requires a non-empty task object")
        _nonempty(record["task"].get("task_id"), "task.task_id")
        _nonempty(record["task"].get("category"), "task.category")
        if record["task"].get("expected_action") not in {"answer", "abstain", "out_of_domain"}:
            raise DataValidationError("task.expected_action must be answer, abstain, or out_of_domain")


def _content_payload(record: dict, kind: str) -> dict:
    keys = {"pretrain": ("text",), "sft": ("messages",), "verifier": ("messages",),
            "preference": ("prompt", "chosen", "rejected"), "rl": ("prompt",)}[kind]
    return {key: record[key] for key in keys}


def validate_manifest(manifest_path: str | Path) -> dict:
    """Validate rights, schemas, hashes, exact duplicate content and family leakage.

    The SQLite index bounds memory use. Exact canonical-content matching cannot
    detect paraphrases or unmarked problem variants; assign their shared family.
    """
    path, manifest = _read_manifest(manifest_path)
    split_records: dict[str, int] = {}
    stage_records: dict[str, int] = {}
    count = 0
    source_ids: set[str] = set()
    source_hashes: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="forge1-validate-") as temp:
        db = sqlite3.connect(Path(temp) / "index.sqlite")
        try:
            db.execute("CREATE TABLE records (id TEXT PRIMARY KEY, digest TEXT UNIQUE, split TEXT, location TEXT)")
            db.execute("CREATE TABLE families (family TEXT PRIMARY KEY, split TEXT)")
            db.execute("CREATE TABLE prompts (digest TEXT PRIMARY KEY, split TEXT, location TEXT)")
            for source in manifest["sources"]:
                if not isinstance(source, dict):
                    raise DataValidationError("Each manifest source must be an object")
                source_id = _nonempty(source.get("source_id"), "source_id")
                if source_id in source_ids:
                    raise DataValidationError(f"Duplicate source_id: {source_id}")
                source_ids.add(source_id)
                split, kind = source.get("split"), source.get("kind")
                if split not in SPLITS or kind not in STAGES:
                    raise DataValidationError(f"Invalid split/kind for {source_id}")
                if source.get("domain") not in DOMAINS:
                    raise DataValidationError(f"Unapproved domain for {source_id}; expected {sorted(DOMAINS)}")
                _nonempty(source.get("provenance"), "source.provenance")
                _nonempty(source.get("license"), "source.license")
                rights = source.get("rights")
                if not isinstance(rights, dict) or rights.get("approved") is not True:
                    raise DataValidationError(f"Explicit rights.approved=true required for {source_id}")
                if rights.get("basis") not in {"owned", "licensed", "permission", "authored"}:
                    raise DataValidationError("rights.basis must be owned, licensed, permission, or authored")
                _nonempty(rights.get("holder"), "rights.holder")
                source_path = _source_path(path, source)
                expected = source.get("sha256")
                if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
                    raise DataValidationError(f"Lowercase SHA-256 required for {source_id}")
                if not source_path.is_file():
                    raise DataValidationError(f"Missing source file: {source_path}")
                if sha256_file(source_path) != expected:
                    raise DataValidationError(f"SHA-256 mismatch: {source_path}")
                if expected in source_hashes:
                    raise DataValidationError(f"Duplicate source content: {source_id} and {source_hashes[expected]}")
                source_hashes[expected] = source_id
                source_count = 0
                for line, record in _iter_records(source_path):
                    location = f"{source_path}:{line}"
                    try:
                        _validate_record(record, kind)
                        family = _nonempty(record.get("document_family", source.get("document_family")), "document_family")
                        row = db.execute("SELECT split FROM families WHERE family=?", (family,)).fetchone()
                        if row and row[0] != split:
                            raise DataValidationError(f"Document family leaks across splits: {family}")
                        db.execute("INSERT OR IGNORE INTO families VALUES (?, ?)", (family, split))
                        if kind != "pretrain":
                            prompt = record.get("prompt", record.get("messages", [])[:-1])
                            prompt_digest = hashlib.sha256(_canonical(prompt)).hexdigest()
                            prior_prompt = db.execute("SELECT split, location FROM prompts WHERE digest=?", (prompt_digest,)).fetchone()
                            if prior_prompt and prior_prompt[0] != split:
                                raise DataValidationError(f"Prompt leaks across splits; first seen at {prior_prompt[1]}")
                            db.execute("INSERT OR IGNORE INTO prompts VALUES (?, ?, ?)", (prompt_digest, split, location))
                        digest = hashlib.sha256(_canonical(_content_payload(record, kind))).hexdigest()
                        prior = db.execute("SELECT location, split FROM records WHERE digest=?", (digest,)).fetchone()
                        if prior:
                            raise DataValidationError(f"Duplicate content (possible split leakage); first seen at {prior[0]} ({prior[1]})")
                        try:
                            db.execute("INSERT INTO records VALUES (?, ?, ?, ?)", (record["id"], digest, split, location))
                        except sqlite3.IntegrityError as error:
                            raise DataValidationError(f"Duplicate record id: {record['id']}") from error
                    except (DataValidationError, TypeError, ValueError) as error:
                        raise DataValidationError(f"{location}: {error}") from error
                    count += 1
                    source_count += 1
                    split_records[split] = split_records.get(split, 0) + 1
                    stage_records[kind] = stage_records.get(kind, 0) + 1
                if source_count == 0:
                    raise DataValidationError(f"Source has no records: {source_path}")
                if sha256_file(source_path) != expected:
                    raise DataValidationError(f"Source changed during validation: {source_path}")
                db.commit()
        finally:
            db.close()
    return {"version": 1, "fingerprint": hashlib.sha256(_canonical(manifest)).hexdigest(),
            "source_count": len(source_ids), "record_count": count, "split_records": split_records,
            "stage_records": stage_records, "is_fixture": manifest.get("is_fixture", False)}


def iter_training_texts(manifest_path: str | Path) -> Iterator[str]:
    """Tokenizer corpus iterator. Call validate_manifest before using it."""
    path, manifest = _read_manifest(manifest_path)
    for source in manifest["sources"]:
        if source["split"] != "train":
            continue
        for _, record in _iter_records(_source_path(path, source)):
            if source["kind"] == "pretrain":
                yield record["text"]
            else:
                for message in record.get("messages", record.get("prompt", [])):
                    yield message["content"]
                    if message.get("tool_calls"):
                        yield _canonical({"tool_calls": message["tool_calls"]}).decode("utf-8")
                for field in ("chosen", "rejected"):
                    if field in record:
                        yield record[field]


def _sequence(tokens: list[int], targets: list[bool], seq_length: int, tokenizer: TokenizerProtocol) -> dict[str, np.ndarray]:
    if len(tokens) < 2 or len(tokens) > seq_length:
        raise DataValidationError(f"Sequence requires 2..{seq_length} tokens; got {len(tokens)}")
    input_ids = np.full(seq_length, tokenizer.pad_id, dtype=np.int32)
    labels = np.full(seq_length, IGNORE_INDEX, dtype=np.int32)
    attention_mask = np.zeros(seq_length, dtype=np.int32)
    length = len(tokens)
    input_ids[:length] = tokens
    attention_mask[:length] = 1
    # Labels align with their input tokens. The model/loss shifts exactly once.
    labels[:length] = [token if supervise else IGNORE_INDEX for token, supervise in zip(tokens, targets)]
    labels[0] = IGNORE_INDEX
    if not np.any(labels != IGNORE_INDEX):
        raise DataValidationError("Prepared sequence contains no supervised target")
    return {"input_ids": input_ids, "labels": labels, "attention_mask": attention_mask}


def _auxiliary(record: dict, position: int) -> dict[str, np.ndarray]:
    return {"aux_position": np.asarray(position, dtype=np.int64),
        "constraint_labels": np.asarray([(-1 if v is None else v) for v in record.get("constraint_labels", [-1] * 4)], dtype=np.float32),
        "si_dimensions": np.asarray([(np.nan if v is None else v) for v in record.get("si_dimensions", [None] * 7)], dtype=np.float32),
        "domain_label": np.asarray(record.get("domain_label", -1), dtype=np.int64),
        "verifier_label": np.asarray(-1 if record.get("verifier_label") is None else record["verifier_label"], dtype=np.float32)}


class _ArrayWriter:
    def __init__(self, directory: Path):
        self.directory = directory
        self.streams: dict = {}
        self.specs: dict = {}
        self.count = 0

    def append(self, example: dict[str, np.ndarray]) -> None:
        if self.count and set(example) != set(self.specs):
            raise DataValidationError("Inconsistent dataset array fields")
        for name, value in example.items():
            if name not in self.streams:
                self.specs[name] = {"dtype": str(value.dtype), "shape": list(value.shape)}
                self.streams[name] = (self.directory / f"{name}.raw").open("wb")
            if str(value.dtype) != self.specs[name]["dtype"] or list(value.shape) != self.specs[name]["shape"]:
                raise DataValidationError(f"Inconsistent shape/dtype for {name}")
            self.streams[name].write(value.tobytes())
        self.count += 1

    def close(self) -> None:
        for stream in self.streams.values():
            stream.close()

    def finalize(self) -> dict:
        self.close()
        for name, spec in self.specs.items():
            shape = (self.count, *spec["shape"])
            source = np.memmap(self.directory / f"{name}.raw", mode="r", dtype=spec["dtype"], shape=shape)
            target = np.lib.format.open_memmap(self.directory / f"{name}.npy", mode="w+", dtype=spec["dtype"], shape=shape)
            for start in range(0, self.count, 1024):
                target[start:start + 1024] = source[start:start + 1024]
            target.flush()
            del source, target
            (self.directory / f"{name}.raw").unlink()
            spec["shape"] = list(shape)
            spec["sha256"] = sha256_file(self.directory / f"{name}.npy")
        return self.specs


def prepare_dataset(manifest_path: str | Path, tokenizer: TokenizerProtocol,
                    output_dir: str | Path, seq_length: int, stage: str = "pretrain",
                    split: str = "train") -> dict:
    """Atomically create an immutable mmap dataset; reject existing destinations."""
    if stage not in STAGES or split not in SPLITS:
        raise DataValidationError("Invalid preparation stage/split")
    if type(seq_length) is not int or seq_length < 2:
        raise DataValidationError("seq_length must be an integer of at least 2")
    report = validate_manifest(manifest_path)
    manifest_path, manifest = _read_manifest(manifest_path)
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Prepared destination already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    writer = _ArrayWriter(temporary)
    record_count = 0
    target_tokens = 0
    try:
        with (temporary / "records.jsonl").open("wb") as index:
            for source in manifest["sources"]:
                if source["split"] != split or source["kind"] != stage:
                    continue
                source_path = _source_path(manifest_path, source)
                for line, record in _iter_records(source_path):
                    start_index = writer.count
                    try:
                        if stage == "pretrain":
                            tokens = tokenizer.encode(record["text"], add_bos=True, add_eos=True)
                            for start in range(0, len(tokens) - 1, seq_length - 1):
                                window = tokens[start:start + seq_length]
                                arrays = _sequence(window, [True] * len(window), seq_length, tokenizer)
                                target_tokens += int(np.sum(arrays["labels"] != IGNORE_INDEX))
                                writer.append(arrays)
                        elif stage in {"sft", "verifier"}:
                            tokens, targets = serialize_messages(record["messages"], tokenizer)
                            # Aux heads inspect turn_end, after the complete answer.
                            # EOS follows it, retained as a same-position LM target.
                            tokens.append(tokenizer.eos_id)
                            targets.append(True)
                            arrays = _sequence(tokens, targets, seq_length, tokenizer)
                            arrays.update(_auxiliary(record, len(tokens) - 2))
                            target_tokens += int(np.sum(arrays["labels"] != IGNORE_INDEX))
                            writer.append(arrays)
                        elif stage == "preference":
                            arrays = {}
                            prompt_length = len(serialize_messages(record["prompt"], tokenizer)[0])
                            for choice in ("chosen", "rejected"):
                                messages = record["prompt"] + [{"role": "assistant", "content": record[choice]}]
                                tokens, targets = serialize_messages(messages, tokenizer)
                                targets[:prompt_length] = [False] * prompt_length
                                tokens.append(tokenizer.eos_id)
                                targets.append(True)
                                part = _sequence(tokens, targets, seq_length, tokenizer)
                                target_tokens += int(np.sum(part["labels"] != IGNORE_INDEX))
                                arrays.update({f"{choice}_{key}": value for key, value in part.items()})
                            writer.append(arrays)
                        else:
                            tokens = encode_chat(record["prompt"], tokenizer)
                            if len(tokens) > seq_length:
                                raise DataValidationError(f"RL prompt has {len(tokens)} tokens; limit is {seq_length}")
                            ids = np.full(seq_length, tokenizer.pad_id, dtype=np.int32)
                            ids[:len(tokens)] = tokens
                            mask = np.zeros(seq_length, dtype=np.int32)
                            mask[:len(tokens)] = 1
                            writer.append({"input_ids": ids, "attention_mask": mask,
                                           "record_offset": np.asarray(index.tell(), dtype=np.int64)})
                        entry = {"record_id": record["id"], "source_id": source["source_id"],
                            "document_family": record.get("document_family", source.get("document_family")),
                            "start": start_index, "count": writer.count - start_index}
                        if stage == "rl":
                            entry["task"] = record["task"]
                        index.write(_canonical(entry) + b"\n")
                    except (ValueError, TypeError) as error:
                        raise DataValidationError(f"{source_path}:{line}: {error}; no records were silently discarded") from error
                    record_count += 1
        if writer.count == 0:
            raise DataValidationError(f"No {stage}/{split} records in manifest")
        arrays = writer.finalize()
        after = validate_manifest(manifest_path)
        if after["fingerprint"] != report["fingerprint"]:
            raise DataValidationError("Manifest changed during preparation")
        metadata = {"format": "forge1-prepared", "version": 1, "stage": stage, "split": split,
            "seq_length": seq_length, "sequence_count": writer.count, "record_count": record_count,
            "supervised_token_count": target_tokens, "manifest_fingerprint": report["fingerprint"],
            "tokenizer_fingerprint": tokenizer.fingerprint, "tokenizer_vocab_size": tokenizer.vocab_size,
            "is_fixture": report["is_fixture"], "document_isolation": True, "arrays": arrays,
            "records_sha256": sha256_file(temporary / "records.jsonl")}
        metadata["fingerprint"] = hashlib.sha256(_canonical(metadata)).hexdigest()
        (temporary / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        tokenizer.save(temporary / "tokenizer.json")
        os.rename(temporary, output_dir)
        return metadata
    except BaseException:
        writer.close()
        # Only the freshly created temporary directory, never a user's destination.
        shutil.rmtree(temporary)
        raise


class PreparedDataset:
    """Read-only mmap arrays. Each item is numpy arrays/scalars, plus RL task data."""

    def __init__(self, path: str | Path, verify_hashes: bool = True):
        self.path = Path(path).resolve()
        self.metadata = json.loads((self.path / "metadata.json").read_text(encoding="utf-8"))
        if self.metadata.get("format") != "forge1-prepared" or self.metadata.get("version") != 1:
            raise DataValidationError("Unsupported prepared dataset format/version")
        fingerprint = self.metadata.get("fingerprint")
        expected = hashlib.sha256(_canonical({k: v for k, v in self.metadata.items() if k != "fingerprint"})).hexdigest()
        if fingerprint != expected:
            raise DataValidationError("Prepared metadata fingerprint mismatch")
        self.fingerprint = fingerprint
        tokenizer = load_tokenizer(self.path / "tokenizer.json")
        if tokenizer.fingerprint != self.metadata["tokenizer_fingerprint"]:
            raise DataValidationError("Prepared tokenizer fingerprint mismatch")
        self.arrays = {}
        for name, spec in self.metadata["arrays"].items():
            if name not in {"input_ids", "labels", "attention_mask", "aux_position", "constraint_labels", "si_dimensions", "domain_label", "verifier_label",
                "chosen_input_ids", "chosen_labels", "chosen_attention_mask", "rejected_input_ids", "rejected_labels", "rejected_attention_mask", "record_offset"}:
                raise DataValidationError(f"Unsupported dataset array: {name}")
            array_path = self.path / f"{name}.npy"
            if verify_hashes and sha256_file(array_path) != spec["sha256"]:
                raise DataValidationError(f"Prepared array hash mismatch: {name}")
            array = np.load(array_path, mmap_mode="r", allow_pickle=False)
            if list(array.shape) != spec["shape"] or str(array.dtype) != spec["dtype"]:
                raise DataValidationError(f"Prepared array shape/dtype mismatch: {name}")
            if array.ndim == 0 or array.shape[0] != self.metadata["sequence_count"]:
                raise DataValidationError(f"Prepared array record count mismatch: {name}")
            self.arrays[name] = array
        if self.metadata["stage"] == "preference":
            required = {f"{choice}_{name}" for choice in ("chosen", "rejected") for name in ("input_ids", "labels", "attention_mask")}
        elif self.metadata["stage"] == "rl":
            required = {"input_ids", "attention_mask", "record_offset"}
        else:
            required = {"input_ids", "labels", "attention_mask"}
        if not required.issubset(self.arrays):
            raise DataValidationError(f"Prepared dataset lacks required arrays: {sorted(required - self.arrays.keys())}")
        for name in required - {"record_offset"}:
            if self.arrays[name].shape != (len(self), self.metadata["seq_length"]):
                raise DataValidationError(f"Prepared sequence shape mismatch: {name}")
        if verify_hashes and sha256_file(self.path / "records.jsonl") != self.metadata["records_sha256"]:
            raise DataValidationError("Prepared record index hash mismatch")

    def __len__(self) -> int:
        return int(self.metadata["sequence_count"])

    def __getitem__(self, index: int) -> dict:
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        # Copies are writable and avoid undefined behavior in torch.from_numpy.
        item = {name: np.array(array[index], copy=True) for name, array in self.arrays.items() if name != "record_offset"}
        if self.metadata["stage"] == "rl":
            with (self.path / "records.jsonl").open("rb") as stream:
                stream.seek(int(self.arrays["record_offset"][index]))
                record = json.loads(stream.readline())
            item.update(task=record["task"], record_id=record["record_id"])
        return item


PreferenceDataset = PreparedDataset
