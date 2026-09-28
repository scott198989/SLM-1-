from unittest.mock import patch

import pytest
import torch

from forge1.checkpoint import capture_rng, restore_rng
from forge1.config import ModelConfig
from forge1.training import TrainConfig


def test_cpu_checkpoint_does_not_touch_available_cuda_devices():
    with patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.get_rng_state_all") as every, \
         patch("torch.cuda.get_rng_state") as one:
        state = capture_rng("cpu")
        assert state["cuda"] == [] and state["cuda_device"] is None
        every.assert_not_called()
        one.assert_not_called()


def test_cuda_checkpoint_only_reads_and_restores_its_rank_local_device():
    rng = torch.tensor([1, 2, 3], dtype=torch.uint8)
    with patch("torch.cuda.get_rng_state", return_value=rng) as read, \
         patch("torch.cuda.get_rng_state_all") as all_devices:
        state = capture_rng("cuda:2")
        read.assert_called_once_with(2)
        all_devices.assert_not_called()
    with patch("torch.cuda.is_available", return_value=True), patch("torch.cuda.set_rng_state") as write:
        restore_rng(state)
        assert write.call_args.kwargs["device"] == 2
        assert torch.equal(write.call_args.args[0], rng)


@pytest.mark.parametrize("name", ["allow_fixture_data", "gradient_checkpointing"])
@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_training_flags_require_actual_json_booleans(name, value):
    with pytest.raises(ValueError, match="boolean"):
        TrainConfig("model.json", "tokenizer.json", "dataset", "run", **{name: value})


@pytest.mark.parametrize("name", ["dropout", "rope_theta", "initializer_std", "rms_norm_eps"])
def test_model_config_rejects_nonfinite_numeric_fields(name):
    with pytest.raises(ValueError, match="finite"):
        ModelConfig(**{name: float("nan")})
