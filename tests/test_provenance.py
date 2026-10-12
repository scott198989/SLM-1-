"""Fixture ancestry cannot disappear merely because a later manifest is unflagged.

Every corpus here is authored software-test data. The unflagged controls exist
only to exercise metadata boundaries; they are not genuine production datasets.
"""

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
import torch

from forge1.checkpoint import load_checkpoint
from forge1.config import ModelConfig
from forge1.data import PreparedDataset, prepare_dataset
from forge1.rl import GRPOConfig, train_grpo
from forge1.tokenizer import ByteTokenizer
from forge1.training import TrainConfig, train


def _prepare(root, tokenizer, kind="pretrain", *, is_fixture=False):
    root.mkdir(parents=True)
    if kind == "pretrain":
        record = {"id": "authored-control", "text": "Authored test only. Torque equals force times radius."}
    elif kind == "preference":
        record = {"id": "authored-pair", "prompt": [{"role": "user", "content": "Torque unit?"}],
                  "chosen": "N*m", "rejected": "V"}
    else:
        prompt = "Find torque for perpendicular 4 N at 0.5 m."
        record = {"id": "authored-rl", "prompt": [{"role": "user", "content": prompt}], "task": {
            "task_id": "provenance-control", "source_family": "provenance-control",
            "category": "mechanics", "prompt": prompt, "reference": 2.0, "expected_unit": "N*m",
            "tolerance": {"absolute": 1e-6, "relative": 1e-6}, "required_assumptions": [],
            "expected_action": "answer"}}
    source = root / "source.jsonl"
    source.write_text(json.dumps(record) + "\n", encoding="utf-8")
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "is_fixture": is_fixture, "sources": [{
        "path": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "split": "train", "kind": kind, "source_id": root.name, "document_family": "provenance-control",
        "provenance": "Authored regression data; fixture flag intentionally varied only to test ancestry handling",
        "license": "Approved for local software tests only", "domain": "mechatronics",
        "rights": {"approved": True, "basis": "authored", "holder": "Regression-test author"},
    }]}), encoding="utf-8")
    prepare_dataset(manifest, tokenizer, root / "prepared", seq_length=128, stage=kind)
    return str(root / "prepared")


@pytest.fixture(scope="module")
def ancestry_models(tmp_path_factory):
    root = tmp_path_factory.mktemp("provenance-controls")
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(min(previous_threads, 2))
    tokenizer = ByteTokenizer()
    tokenizer_path = root / "tokenizer.json"
    tokenizer.save(tokenizer_path)
    model = ModelConfig(vocab_size=288, d_model=16, n_heads=2, n_kv_heads=1,
        intermediate_size=32, stem_layers=0, core_layers=1, speaker_layers=0,
        max_seq_len=128, default_loops=1, max_loops=4, ledger_rank=4, dropout=0.0)
    model_path = root / "model.json"
    model_path.write_text(json.dumps(model.to_dict()), encoding="utf-8")
    fixture_data = _prepare(root / "flagged-data", tokenizer, is_fixture=True)
    control_data = _prepare(root / "unflagged-data", tokenizer, is_fixture=False)
    template = TrainConfig(model_config=str(model_path), tokenizer=str(tokenizer_path),
        dataset=control_data, output_dir=str(root / "control-base"), steps=1, warmup_steps=0,
        batch_size=1, gradient_accumulation=1, checkpoint_every=1, evaluate_every=1,
        device="cpu", precision="fp32", gradient_checkpointing=False,
        loop_min=1, loop_max=1, aux_weight=0, allow_fixture_data=False)
    control = train(template)["checkpoint"]
    fixture = train(replace(template, dataset=fixture_data, output_dir=str(root / "fixture-base"),
                            allow_fixture_data=True))["checkpoint"]
    assert load_checkpoint(control)["is_fixture"] is False
    assert load_checkpoint(fixture)["is_fixture"] is True
    yield {"template": template, "tokenizer": tokenizer, "control": control,
           "fixture": fixture, "root": root}
    torch.set_num_threads(previous_threads)


@pytest.mark.parametrize("dependency", ["initialization", "reference", "teacher"])
@pytest.mark.parametrize("allow_fixture", [False, True])
def test_training_preserves_fixture_ancestry_on_unflagged_data(tmp_path, ancestry_models, dependency, allow_fixture):
    setup = ancestry_models
    overrides = {"output_dir": str(tmp_path / "run"), "init_checkpoint": setup["control"],
                 "allow_fixture_data": allow_fixture}
    if dependency == "initialization":
        overrides.update(stage="cpt", init_checkpoint=setup["fixture"])
    elif dependency == "reference":
        overrides.update(stage="dpo", reference_checkpoint=setup["fixture"],
                         dataset=_prepare(tmp_path / "preference", setup["tokenizer"], "preference"))
    else:
        overrides.update(stage="distill", teacher_checkpoint=setup["fixture"])
    config = replace(setup["template"], **overrides)
    assert PreparedDataset(config.dataset).metadata["is_fixture"] is False
    if not allow_fixture:
        with pytest.raises(ValueError, match="Fixture checkpoint ancestry"):
            train(config)
        assert not (Path(config.output_dir) / "last.pt").exists()
        assert not (Path(config.output_dir) / "metrics.jsonl").exists()
    else:
        result = train(config)
        saved = load_checkpoint(result["checkpoint"])
        assert saved["step"] == 1
        assert saved["is_fixture"] is True
        assert saved["training_config"]["allow_fixture_data"] is True


@pytest.mark.parametrize("dependency", ["initialization", "reference"])
@pytest.mark.parametrize("allow_fixture", [False, True])
def test_grpo_preserves_fixture_ancestry_on_unflagged_data(tmp_path, ancestry_models, dependency, allow_fixture):
    setup = ancestry_models
    data = _prepare(tmp_path / "rl-source", setup["tokenizer"], "rl")
    checkpoints = {"init_checkpoint": setup["control"], "reference_checkpoint": setup["control"]}
    checkpoints["init_checkpoint" if dependency == "initialization" else "reference_checkpoint"] = setup["fixture"]
    config = GRPOConfig(**checkpoints, tokenizer=setup["template"].tokenizer, dataset=data,
        output_dir=str(tmp_path / "rl-run"), steps=1, batch_size=1, group_size=2,
        max_new_tokens=2, mode="fast", precision="fp32", device="cpu", checkpoint_every=1,
        gradient_checkpointing=False, allow_fixture_data=allow_fixture)
    assert PreparedDataset(config.dataset).metadata["is_fixture"] is False
    if not allow_fixture:
        with pytest.raises(ValueError, match="Fixture checkpoint ancestry"):
            train_grpo(config)
        assert not (Path(config.output_dir) / "last.pt").exists()
    else:
        result = train_grpo(config)
        saved = load_checkpoint(result["checkpoint"])
        assert saved["step"] == 1
        assert saved["is_fixture"] is True
        # Two generated byte tokens cannot form a valid structured task answer.
        # Even a zero-policy-signal checkpoint must retain fixture ancestry.
        assert saved["optimizer_updates"] == 0


@pytest.mark.parametrize("field", ["allow_fixture_data", "gradient_checkpointing"])
@pytest.mark.parametrize("invalid", ["false", "true", 0, 1, None])
def test_training_boolean_flags_reject_truthy_strings_and_numeric_values(field, invalid):
    values = {"model_config": "model.json", "tokenizer": "tokenizer.json", "dataset": "data",
              "output_dir": "run", field: invalid}
    with pytest.raises(ValueError, match="boolean"):
        TrainConfig(**values)
