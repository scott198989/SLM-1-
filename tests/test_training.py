"""Real CPU training integrations on explicitly authored, temporary fixture data."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
import torch

from forge1.checkpoint import load_checkpoint, model_from_checkpoint
from forge1.config import ModelConfig
from forge1.data import PreparedDataset, prepare_dataset
from forge1.model import ForgeModel
from forge1.tokenizer import ByteTokenizer
from forge1.training import TrainConfig, _loss, collate, train, validate


def _prepared(root, tokenizer, stage="pretrain", *, split="train", records=None, seq_length=64):
    root.mkdir(parents=True, exist_ok=True)
    if records is None:
        records = [{"id": "authored-pattern", "text": "Torque equals force times radius. " * 12}]
    source = root / "source.jsonl"
    source.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({
        "version": 1, "is_fixture": True, "sources": [{
            "path": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "split": split, "kind": stage, "source_id": f"authored-{root.name}",
            "document_family": f"authored-family-{root.name}",
            "provenance": "Authored deterministic software-test text; not an engineering corpus",
            "license": "Private unit-test fixture", "domain": "mechatronics",
            "rights": {"approved": True, "basis": "authored", "holder": "Fixture author"},
        }],
    }), encoding="utf-8")
    prepare_dataset(manifest, tokenizer, root / "prepared", seq_length=seq_length, stage=stage, split=split)
    return str(root / "prepared")


@pytest.fixture
def setup(tmp_path):
    config = ModelConfig(vocab_size=288, d_model=32, n_heads=4, n_kv_heads=2,
                         intermediate_size=80, stem_layers=1, core_layers=1,
                         speaker_layers=1, max_seq_len=128, default_loops=1,
                         max_loops=4, ledger_rank=4, dropout=0.1)
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    tokenizer = ByteTokenizer()
    tokenizer_path = tmp_path / "tokenizer.json"
    tokenizer.save(tokenizer_path)
    data = _prepared(tmp_path / "pretrain-source", tokenizer)
    config = TrainConfig(
        model_config=str(model_path), tokenizer=str(tokenizer_path), dataset=data,
        output_dir=str(tmp_path / "run"), steps=4, batch_size=1, gradient_accumulation=2,
        learning_rate=0.003, warmup_steps=0, weight_decay=0.01, grad_clip=1.0,
        precision="fp32", device="cpu", checkpoint_every=3, evaluate_every=100,
        gradient_checkpointing=False, loop_min=1, loop_max=2, aux_weight=0,
        allow_fixture_data=True,
    )
    return tmp_path, tokenizer, config


def _messages(answer="Torque is 2 N m."):
    return [{"role": "user", "content": "Torque for 4 N at 0.5 m?"},
            {"role": "assistant", "content": answer}]


def _assert_nested_exact(a, b):
    if isinstance(a, torch.Tensor):
        assert torch.equal(a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a:
            _assert_nested_exact(a[key], b[key])
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b)
        for first, second in zip(a, b, strict=True):
            _assert_nested_exact(first, second)
    else:
        assert a == b


def _base_run(config):
    return train(replace(config, output_dir=str(Path(config.output_dir).parent / "base"), steps=1))


def _jointly_prepare(root, tokenizer, training_path, validation_path):
    """Use one manifest so the real intake audits train/validation together."""
    root.mkdir(parents=True, exist_ok=True)
    sources = []
    for prepared in (training_path, validation_path):
        manifest_path = Path(prepared).parent / "manifest.json"
        for source in json.loads(manifest_path.read_text(encoding="utf-8"))["sources"]:
            sources.append({**source, "path": str((manifest_path.parent / source["path"]).resolve())})
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "is_fixture": True, "sources": sources}), encoding="utf-8")
    paths = []
    for split, previous in (("train", training_path), ("validation", validation_path)):
        metadata = PreparedDataset(previous).metadata
        destination = root / split
        prepare_dataset(manifest, tokenizer, destination, seq_length=metadata["seq_length"],
                        stage=metadata["stage"], split=split)
        paths.append(str(destination))
    return tuple(paths)


def test_actual_pretraining_reduces_held_out_pattern_loss(setup):
    root, tokenizer, config = setup
    validation = _prepared(root / "validation-source", tokenizer, split="validation", records=[
        {"id": "held-out-pattern", "text": "Torque equals force times radius. " * 3},
    ])
    training_data, validation = _jointly_prepare(root / "joint-pattern", tokenizer, config.dataset, validation)
    config = replace(config, dataset=training_data, steps=20, learning_rate=0.006, loop_max=4,
                     validation_dataset=validation, evaluate_every=20)
    torch.manual_seed(config.seed)
    initial = ForgeModel(ModelConfig.from_json(config.model_config))
    before_by_depth = {depth: validate(initial, PreparedDataset(validation), replace(config, loop_max=depth),
                                      torch.device("cpu"))["validation_loss"] for depth in (1, 2, 4)}
    before = before_by_depth[4]
    result = train(config)
    after = result["metrics"]["validation_loss"]
    assert after < before - 0.8
    assert result["step"] == 20
    assert result["trained_tokens"] > 0
    assert result["reason"] == "completed_schedule"
    payload = load_checkpoint(result["checkpoint"])
    assert payload["is_fixture"] is True
    assert all(group["foreach"] is False for group in payload["optimizer"]["param_groups"])
    learned, _ = model_from_checkpoint(result["checkpoint"])
    after_by_depth = {depth: validate(learned, PreparedDataset(validation), replace(config, loop_max=depth),
                                     torch.device("cpu"))["validation_loss"] for depth in (1, 2, 4)}
    for depth in (1, 2, 4):
        assert after_by_depth[depth] < before_by_depth[depth] - 0.8
    print(json.dumps({"authored_pattern_before": before_by_depth, "authored_pattern_after": after_by_depth}))


def test_resume_matches_uninterrupted_weights_optimizer_rng_and_data_cursor(setup):
    root, _, config = setup
    config = replace(config, steps=7, gradient_checkpointing=True)
    uninterrupted = train(replace(config, output_dir=str(root / "continuous")))
    interrupted = train(config, stop_after=3)
    assert interrupted["step"] == 3
    assert interrupted["reason"] == "requested_step_budget"
    resumed = train(config, resume=interrupted["checkpoint"])
    expected, actual = load_checkpoint(uninterrupted["checkpoint"]), load_checkpoint(resumed["checkpoint"])
    for key in ("model", "optimizer", "rng_by_rank", "data_cursor", "trained_tokens", "step"):
        _assert_nested_exact(expected[key], actual[key])


def test_sft_trains_annotated_heads_and_records_metrics(setup):
    root, tokenizer, config = setup
    initial = _base_run(config)
    sft_data = _prepared(root / "sft-source", tokenizer, "sft", seq_length=96, records=[{
        "id": "sft-evidence", "messages": _messages(), "constraint_labels": [1, 1, None, 0],
        "si_dimensions": [1, 2, -2, 0, 0, 0, 0], "domain_label": 0, "verifier_label": 1,
    }])
    sft = replace(config, stage="sft", dataset=sft_data, init_checkpoint=initial["checkpoint"],
                  output_dir=str(root / "sft-run"), steps=2, aux_weight=1.0)
    result = train(sft)
    for key in ("constraint_labels", "si_dimensions", "domain_label", "verifier_label"):
        assert key in result["metrics"]["last_microbatch_details_rank0"]
    old, new = load_checkpoint(initial["checkpoint"]), load_checkpoint(result["checkpoint"])
    assert not torch.equal(old["model"]["verifier_head.weight"], new["model"]["verifier_head.weight"])


def test_verifier_stage_does_not_imitate_labeled_incorrect_solution(setup):
    root, tokenizer, config = setup
    data = _prepared(root / "verifier-source", tokenizer, "verifier", seq_length=96, records=[{
        "id": "incorrect-solution", "messages": _messages("Torque is 99 volts."), "verifier_label": 0,
    }])
    verifier = replace(config, stage="verifier", dataset=data, aux_weight=1.0)
    model = ForgeModel(ModelConfig.from_json(config.model_config)).eval()
    batch = collate(PreparedDataset(data), [0], torch.device("cpu"))
    original, _ = _loss(model, batch, verifier, loops=1)
    changed = {**batch, "labels": batch["labels"].clone()}
    changed["labels"][changed["labels"].ne(-100)] = 100
    modified, _ = _loss(model, changed, verifier, loops=1)
    torch.testing.assert_close(original, modified)
    initial = _base_run(config)
    result = train(replace(verifier, init_checkpoint=initial["checkpoint"], steps=1,
                           output_dir=str(root / "verifier-run")))
    assert result["step"] == 1 and "verifier_label" in result["metrics"]["last_microbatch_details_rank0"]


def test_dpo_one_update_keeps_reference_frozen(setup, monkeypatch):
    root, tokenizer, config = setup
    initial = _base_run(config)
    data = _prepared(root / "preference-source", tokenizer, "preference", seq_length=96, records=[{
        "id": "preference", "prompt": _messages()[:-1], "chosen": "2 N m", "rejected": "99 volts",
    }])
    import forge1.training as training
    created = []
    def record_model(model_config):
        result = ForgeModel(model_config)
        created.append(result)
        return result
    monkeypatch.setattr(training, "ForgeModel", record_model)
    dpo = replace(config, stage="dpo", dataset=data, init_checkpoint=initial["checkpoint"],
                  reference_checkpoint=initial["checkpoint"], output_dir=str(root / "dpo-run"), steps=1)
    result = train(dpo)
    assert result["step"] == 1 and "preference_margin" in result["metrics"]["last_microbatch_details_rank0"]
    assert len(created) == 2
    assert all(not parameter.requires_grad and parameter.grad is None for parameter in created[1].parameters())
    base = load_checkpoint(initial["checkpoint"])["model"]
    for name, parameter in created[1].state_dict().items():
        assert torch.equal(parameter, base[name])


def test_distillation_one_update_keeps_teacher_frozen(setup, monkeypatch):
    root, _, config = setup
    initial = _base_run(config)
    import forge1.training as training
    created = []
    def record_model(model_config):
        result = ForgeModel(model_config)
        created.append(result)
        return result
    monkeypatch.setattr(training, "ForgeModel", record_model)
    distill = replace(config, stage="distill", init_checkpoint=initial["checkpoint"],
                      teacher_checkpoint=initial["checkpoint"], output_dir=str(root / "distill-run"), steps=1)
    result = train(distill)
    assert result["step"] == 1 and "distillation_loss" in result["metrics"]["last_microbatch_details_rank0"]
    assert len(created) == 2
    assert all(not parameter.requires_grad and parameter.grad is None for parameter in created[1].parameters())


def test_lora_training_and_resume_preserve_frozen_base(setup):
    root, _, config = setup
    initial = _base_run(config)
    config = replace(config, stage="cpt", init_checkpoint=initial["checkpoint"],
                     output_dir=str(root / "lora-run"), lora_rank=4, lora_alpha=8, steps=3)
    interrupted = train(config, stop_after=1)
    result = train(config, resume=interrupted["checkpoint"])
    initial_state = load_checkpoint(initial["checkpoint"])["model"]
    trained = load_checkpoint(result["checkpoint"])
    assert trained["adapter"] == {"rank": 4, "alpha": 8}
    assert torch.equal(trained["model"]["token_embedding.weight"], initial_state["token_embedding.weight"])
    assert any(torch.count_nonzero(value) for name, value in trained["model"].items() if name.endswith(".b"))
    restored, _ = model_from_checkpoint(result["checkpoint"])
    restored.eval()
    assert torch.isfinite(restored(torch.tensor([[1, 42, 2]])).logits).all()


@pytest.mark.parametrize("mutation", ["schedule", "batch", "data", "model", "tokenizer"])
def test_resume_rejects_changed_run_identity(setup, mutation):
    root, tokenizer, config = setup
    interrupted = train(config, stop_after=1)
    if mutation == "schedule":
        config = replace(config, steps=config.steps + 1)
    elif mutation == "batch":
        config = replace(config, batch_size=2)
    elif mutation == "data":
        data = _prepared(root / "changed-source", tokenizer, records=[{"id": "different", "text": "A changed motor torque document."}])
        config = replace(config, dataset=data)
    elif mutation == "model":
        values = ModelConfig.from_json(config.model_config).to_dict()
        values["dropout"] = 0.2
        path = root / "changed-model.json"
        path.write_text(json.dumps(values), encoding="utf-8")
        config = replace(config, model_config=str(path))
    else:
        checkpoint = load_checkpoint(interrupted["checkpoint"])
        checkpoint["tokenizer_fingerprint"] = "mismatch"
        torch.save(checkpoint, interrupted["checkpoint"])
    with pytest.raises(ValueError, match="mismatch|architecture|tokenizer"):
        train(config, resume=interrupted["checkpoint"])


def test_fixture_and_held_out_training_rejected_before_model_creation(setup):
    root, tokenizer, config = setup
    with pytest.raises(ValueError, match="Fixture"):
        train(replace(config, allow_fixture_data=False))
    held_out = _prepared(root / "sealed-source", tokenizer, split="test", records=[{"id": "test-only", "text": "This is sealed test material."}])
    with pytest.raises(ValueError, match="train split"):
        train(replace(config, dataset=held_out))


def test_distillation_rejects_preference_data_before_creating_run(setup):
    root, tokenizer, config = setup
    initial = _base_run(config)
    pairs = _prepared(root / "wrong-distill-source", tokenizer, "preference", seq_length=96, records=[{
        "id": "preference", "prompt": _messages()[:-1], "chosen": "2 N m", "rejected": "99 volts",
    }])
    bad = replace(config, stage="distill", dataset=pairs, init_checkpoint=initial["checkpoint"],
                  teacher_checkpoint=initial["checkpoint"], output_dir=str(root / "bad-distill"))
    with pytest.raises(ValueError, match="stage|Stage"):
        train(bad)
    assert not Path(bad.output_dir).exists()


def test_validation_stage_mismatch_rejected_before_optimizer_updates(setup):
    root, tokenizer, config = setup
    invalid = _prepared(root / "wrong-validation-source", tokenizer, "preference", split="validation", seq_length=96, records=[{
        "id": "validation-pair", "prompt": _messages()[:-1], "chosen": "2 N m", "rejected": "99 volts",
    }])
    bad = replace(config, validation_dataset=invalid, evaluate_every=1)
    with pytest.raises(ValueError, match="stage|Stage"):
        train(bad)
    assert not Path(bad.output_dir).exists()


def test_validation_requires_one_joint_manifest_even_when_each_split_passes_separately(setup):
    root, tokenizer, config = setup
    # The identical underlying document/family is valid in either manifest alone,
    # but would be rejected if both splits were audited together.
    leaked = _prepared(root / "independent-validation", tokenizer, split="validation", records=[{
        "id": "same-document-different-id", "document_family": "authored-family-pretrain-source",
        "text": "Torque equals force times radius. " * 12,
    }])
    assert PreparedDataset(config.dataset).metadata["split"] == "train"
    assert PreparedDataset(leaked).metadata["split"] == "validation"
    with pytest.raises(ValueError, match="jointly audited manifest"):
        train(replace(config, validation_dataset=leaked, evaluate_every=1))
    assert not Path(config.output_dir).exists()


def _unequal_sft(root, tokenizer, split="train"):
    return _prepared(root, tokenizer, "sft", split=split, seq_length=128, records=[
        {"id": "short-evidence", "messages": _messages("2 N m."),
         "constraint_labels": [1, None, None, None], "verifier_label": 1},
        {"id": "long-evidence", "messages": _messages("The torque is 2 N m because force times moment arm is 4 times 0.5."),
         "si_dimensions": [1, 2, -2, 0, 0, 0, 0], "domain_label": 0},
    ])


def test_accumulation_matches_full_batch_with_unequal_targets_sparse_aux_and_intermediates(setup):
    root, tokenizer, config = setup
    model_values = ModelConfig.from_json(config.model_config).to_dict()
    model_values["dropout"] = 0.0  # Dropout draws legitimately differ across batch partitions.
    Path(config.model_config).write_text(json.dumps(model_values), encoding="utf-8")
    initial = _base_run(config)
    dataset = _unequal_sft(root / "unequal-source", tokenizer)
    config = replace(config, stage="sft", dataset=dataset, init_checkpoint=initial["checkpoint"],
                     steps=1, loop_min=2, loop_max=2, aux_weight=0.7, intermediate_weight=0.2)
    micros = train(replace(config, output_dir=str(root / "micro-run"), batch_size=1, gradient_accumulation=2))
    full = train(replace(config, output_dir=str(root / "batch-run"), batch_size=2, gradient_accumulation=1))
    first, second = load_checkpoint(micros["checkpoint"]), load_checkpoint(full["checkpoint"])
    assert first["trained_tokens"] == second["trained_tokens"]
    for key, value in first["optimizer"]["state"].items():
        torch.testing.assert_close(value["exp_avg"], second["optimizer"]["state"][key]["exp_avg"], rtol=1e-4, atol=2e-8)
    for key, value in first["model"].items():
        torch.testing.assert_close(value, second["model"][key], rtol=1e-4, atol=2e-5)


def test_validation_objective_is_independent_of_batch_partition(setup):
    root, tokenizer, config = setup
    validation = PreparedDataset(_unequal_sft(root / "unequal-validation", tokenizer, split="validation"))
    config = replace(config, stage="sft", aux_weight=0.7, intermediate_weight=0.2, loop_max=2)
    model = ForgeModel(ModelConfig.from_json(config.model_config)).eval()
    singles = validate(model, validation, replace(config, batch_size=1), torch.device("cpu"))
    combined = validate(model, validation, replace(config, batch_size=2), torch.device("cpu"))
    assert singles["validation_examples"] == combined["validation_examples"] == 2
    assert singles["validation_loss"] == pytest.approx(combined["validation_loss"], abs=1e-6)


@pytest.mark.parametrize("stage", ["dpo", "distill"])
def test_exact_resume_rejects_frozen_dependency_replaced_at_same_path(setup, stage):
    root, tokenizer, config = setup
    initial = _base_run(config)
    overrides = {"stage": stage, "init_checkpoint": initial["checkpoint"],
                 "output_dir": str(root / "dependency-run"), "steps": 2}
    if stage == "dpo":
        overrides["dataset"] = _prepared(root / "dependency-preference", tokenizer, "preference", seq_length=96, records=[{
            "id": "preference", "prompt": _messages()[:-1], "chosen": "2 N m", "rejected": "99 volts",
        }])
        overrides["reference_checkpoint"] = initial["checkpoint"]
    else:
        overrides["teacher_checkpoint"] = initial["checkpoint"]
    config = replace(config, **overrides)
    interrupted = train(config, stop_after=1)
    replacement = load_checkpoint(initial["checkpoint"])
    replacement["model"]["token_embedding.weight"] = replacement["model"]["token_embedding.weight"] + 0.01
    torch.save(replacement, initial["checkpoint"])
    with pytest.raises(ValueError, match="reference|teacher|dependency|mismatch"):
        train(config, resume=interrupted["checkpoint"])
