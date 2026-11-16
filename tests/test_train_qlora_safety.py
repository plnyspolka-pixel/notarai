"""No model downloads / GPU required; only negative GPU safety checks."""
from __future__ import annotations
import hashlib
import json
from unittest.mock import patch
import pytest
from tools.agent_factory.train_qlora import (
    TrainingBlocked, verify_input, run_training, APPROVAL_ENV, APPROVAL_VALUE
)


def test_gpu_training_never_starts_implicitly(tmp_path):
    with patch.dict("os.environ", {APPROVAL_ENV: ""}):
        with pytest.raises(TrainingBlocked):
            run_training(tmp_path / "no-dataset", tmp_path / "adapter", "a" * 40)


def test_requires_pinned_revision(tmp_path):
    with patch.dict("os.environ", {APPROVAL_ENV: APPROVAL_VALUE}):
        with pytest.raises(TrainingBlocked):
            verify_input(tmp_path, tmp_path / "out", "latest")


def test_rejects_unsigned_dataset_manifest(tmp_path):
    with patch.dict("os.environ", {APPROVAL_ENV: APPROVAL_VALUE}):
        target = tmp_path / "output"
        with pytest.raises(TrainingBlocked):
            verify_input(tmp_path, target, "a" * 40)


def test_only_approved_base_model(tmp_path):
    with pytest.raises(TrainingBlocked):
        run_training(tmp_path, tmp_path / "out", "a" * 40,
                     model_id="unexpected/new-model")


def test_invalid_training_budget_prevents_gpu_code(tmp_path):
    with pytest.raises(TrainingBlocked):
        run_training(tmp_path, tmp_path / "out", "a" * 40, max_steps=0)
