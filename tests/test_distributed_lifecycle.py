"""Failure-path ownership and cleanup checks without creating a real GPU group."""

from contextlib import ExitStack
import json
import os
import signal
from unittest.mock import patch

import pytest
import torch

from forge1 import training
from forge1.config import ModelConfig
from forge1.data import prepare_dataset, sha256_file
from forge1.tokenizer import ByteTokenizer
from forge1.training import TrainConfig, train


def preflight_config():
    return TrainConfig(model_config="unused-model.json", tokenizer="unused-tokenizer.json",
                       dataset="unused-data", output_dir="unused-output", steps=1,
                       warmup_steps=0, device="cpu", precision="fp32")


@pytest.fixture
def tiny_config(tmp_path):
    tokenizer = ByteTokenizer()
    tokenizer.save(tmp_path / "tokenizer.json")
    model = ModelConfig(vocab_size=288, d_model=16, n_heads=2, n_kv_heads=1,
                        intermediate_size=32, stem_layers=0, core_layers=1,
                        speaker_layers=0, max_seq_len=16, ledger_rank=4)
    (tmp_path / "model.json").write_text(json.dumps(model.to_dict()), encoding="utf-8")
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"id": "lifecycle-only", "text": "An authored lifecycle fixture."}) + "\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "is_fixture": True, "sources": [{
        "path": str(source), "sha256": sha256_file(source), "split": "train", "kind": "pretrain",
        "source_id": "lifecycle-test", "document_family": "lifecycle-test-only", "domain": "mechatronics",
        "provenance": "Original software fixture", "license": "Private fixture use",
        "rights": {"approved": True, "basis": "authored", "holder": "Fixture author"}}]}), encoding="utf-8")
    prepare_dataset(manifest, tokenizer, tmp_path / "prepared", seq_length=16)
    return TrainConfig(model_config=str(tmp_path / "model.json"), tokenizer=str(tmp_path / "tokenizer.json"),
                       dataset=str(tmp_path / "prepared"), output_dir=str(tmp_path / "run"),
                       steps=1, warmup_steps=0, gradient_accumulation=1, loop_min=1, loop_max=1,
                       device="cpu", precision="fp32", allow_fixture_data=True)


def distributed_environment():
    return patch.dict(os.environ, {"WORLD_SIZE": "2", "RANK": "0", "LOCAL_RANK": "0"})


def test_preflight_failure_destroys_group_created_by_train():
    state = {"initialized": False}
    def initialize(*args, **kwargs):
        state["initialized"] = True
    def destroy():
        state["initialized"] = False
    with distributed_environment(), \
         patch.object(training.dist, "is_initialized", side_effect=lambda: state["initialized"]), \
         patch.object(training.dist, "init_process_group", side_effect=initialize) as init, \
         patch.object(training.dist, "destroy_process_group", side_effect=destroy) as close, \
         patch.object(training.ModelConfig, "from_json", side_effect=ValueError("synthetic preflight failure")):
        with pytest.raises(ValueError, match="synthetic preflight failure"):
            train(preflight_config())
    init.assert_called_once()
    close.assert_called_once_with()
    assert state["initialized"] is False


def test_failed_group_initialization_cleans_partially_initialized_group():
    state = {"initialized": False}
    def initialize(*args, **kwargs):
        state["initialized"] = True
        raise RuntimeError("partial initialization failure")
    def destroy():
        state["initialized"] = False
    with distributed_environment(), \
         patch.object(training.dist, "is_initialized", side_effect=lambda: state["initialized"]), \
         patch.object(training.dist, "init_process_group", side_effect=initialize), \
         patch.object(training.dist, "destroy_process_group", side_effect=destroy) as close:
        with pytest.raises(RuntimeError, match="partial initialization"):
            train(preflight_config())
    close.assert_called_once_with()
    assert state["initialized"] is False


def test_preflight_failure_preserves_caller_owned_group():
    with distributed_environment(), \
         patch.object(training.dist, "is_initialized", return_value=True), \
         patch.object(training.dist, "init_process_group") as initialize, \
         patch.object(training.dist, "destroy_process_group") as close, \
         patch.object(training.ModelConfig, "from_json", side_effect=ValueError("synthetic preflight failure")):
        with pytest.raises(ValueError, match="synthetic preflight failure"):
            train(preflight_config())
    initialize.assert_not_called()
    close.assert_not_called()


def test_failed_second_handler_install_restores_first_handler_and_closes_group(tiny_config):
    state = {"initialized": False}
    original = signal.signal
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    def install(signum, handler):
        if signum == signal.SIGTERM and getattr(handler, "__name__", "") == "stop_signal":
            raise RuntimeError("second signal installation failed")
        return original(signum, handler)

    def initialize(*args, **kwargs):
        state["initialized"] = True

    def destroy():
        state["initialized"] = False

    with distributed_environment(), \
         patch.object(training.dist, "is_initialized", side_effect=lambda: state["initialized"]), \
         patch.object(training.dist, "init_process_group", side_effect=initialize), \
         patch.object(training.dist, "destroy_process_group", side_effect=destroy) as close, \
         patch.object(training.dist, "barrier"), \
         patch.object(training, "DistributedDataParallel", side_effect=lambda model, **kwargs: model), \
         patch.object(training.signal, "signal", side_effect=install):
        with pytest.raises(RuntimeError, match="second signal installation"):
            train(tiny_config)
    assert {sig: signal.getsignal(sig) for sig in before} == before
    close.assert_called_once_with()
    assert state["initialized"] is False


def test_failed_thermal_guard_start_stops_partially_started_worker():
    class PartialGuard:
        started = False
        closed = False
        def start(self):
            self.started = True
            raise RuntimeError("thermal worker setup failed")
        def close(self):
            self.closed = True

    guard = PartialGuard()
    with patch.object(training, "telemetry_device_id", return_value="GPU-fixture"), \
         patch.object(training, "ThermalGuard", return_value=guard) as create:
        with pytest.raises(RuntimeError, match="thermal worker setup failed"):
            with ExitStack() as cleanup:
                training._start_thermal_guard(cleanup, 83, torch.device("cuda:1"))
    create.assert_called_once_with(83, "GPU-fixture")
    assert guard.started and guard.closed


def test_successful_cpu_training_restores_handlers_and_does_not_destroy_external_resources(tiny_config):
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        with patch.dict(os.environ, {"WORLD_SIZE": "1", "RANK": "0", "LOCAL_RANK": "0"}), \
             patch.object(training.dist, "is_initialized", return_value=False), \
             patch.object(training.dist, "destroy_process_group") as close:
            result = train(tiny_config)
        assert result["step"] == 1 and result["reason"] == "completed_schedule"
        assert result["trained_tokens"] > 0
        assert {sig: signal.getsignal(sig) for sig in before} == before
        close.assert_not_called()
    finally:
        torch.set_num_threads(previous_threads)
