"""Opt-in GPU LoRA training from independently verified synthetic SFT exports.

This file is NOT imported by the MCP worker and cannot train on CI or CPU.
It refuses to start without explicit approval, pinned model revision,
a dedicated CUDA device and a verified manifest with file digests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re


class TrainingBlocked(ValueError):
    pass


APPROVAL_ENV = "AGENT_FORGE_TRAINING_APPROVED"
APPROVAL_VALUE = "I_APPROVE_SYNTHETIC_LORA_GPU"
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA64 = re.compile(r"[a-f0-9]{64}\Z")


def verify_input(dataset: Path, output: Path, revision: str) -> dict:
    """Check manifest before importing expensive or network-enabled ML libraries."""
    source = Path(dataset).expanduser().resolve()
    target = Path(output).expanduser().resolve()
    if os.environ.get(APPROVAL_ENV) != APPROVAL_VALUE:
        raise TrainingBlocked("dedicated-GPU training not operator-approved")
    if not isinstance(revision, str) or not SHA40.fullmatch(revision):
        raise TrainingBlocked("base model must be pinned to a full immutable commit")
    if (not source.is_dir() or source.is_symlink()
            or target.exists() or target == source
            or source in target.parents or target in source.parents):
        raise TrainingBlocked("unsafe input/output directories")
    meta_path = source / "manifest.json"
    if meta_path.is_symlink() or not meta_path.is_file():
        raise TrainingBlocked("missing dataset manifest")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if (meta.get("status") != "VERIFIED_SYNTHETIC_EXPORT_NOT_TRAINED"
            or type(meta.get("examples")) is not int or meta["examples"] < 20
            or type(meta.get("families")) is not int or meta["families"] < 5
            or type(meta.get("train")) is not int or meta["train"] < 1
            or type(meta.get("holdout")) is not int or meta["holdout"] < 1
            or meta["train"] + meta["holdout"] != meta["examples"]):
        raise TrainingBlocked("dataset is unverified or too small")
    families = [set(), set()]
    for ix, name in enumerate(("train", "holdout")):
        path = source / f"{name}.jsonl"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 15_000_000:
            raise TrainingBlocked("missing, oversized or unsafe dataset split")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if meta.get(name + "_sha256") != digest or not SHA64.fullmatch(digest):
            raise TrainingBlocked("dataset checksum mismatch")
        records = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        if len(records) != meta[name]:
            raise TrainingBlocked("dataset row count mismatch")
        for rec in records:
            if not isinstance(rec, dict) or set(rec) != {"messages", "task_family", "role"}:
                raise TrainingBlocked("unexpected dataset example fields")
            messages = rec["messages"]
            if (not isinstance(messages, list) or len(messages) != 3
                    or [m.get("role") for m in messages] != ["system", "user", "assistant"]
                    or any(not isinstance(m.get("content"), str)
                           or not 1 <= len(m["content"]) <= 28_000
                           for m in messages)):
                raise TrainingBlocked("malformed training conversation")
            families[ix].add(rec["task_family"])
    if families[0] & families[1]:
        raise TrainingBlocked("task family leaked into holdout")
    return {
        "train": meta["train"], "holdout": meta["holdout"],
        "families": meta["families"],
        "dataset_sha256": hashlib.sha256(
            (meta["train_sha256"] + meta["holdout_sha256"]).encode()).hexdigest()
    }


def run_training(dataset: Path, output: Path, revision: str,
                 model_id: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
                 max_steps: int = 120) -> None:
    if model_id != "Qwen/Qwen2.5-Coder-7B-Instruct":
        raise TrainingBlocked("non-approved base model")
    if type(max_steps) is not int or not 1 <= max_steps <= 200:
        raise TrainingBlocked("training step budget outside approved range")
    metadata = verify_input(dataset, output, revision)
    # The import of GPU libraries happens AFTER all opt-in and data checks.
    import torch
    if not torch.cuda.is_available():
        raise TrainingBlocked("CUDA GPU required; no CPU training fallback")
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
        Trainer, TrainingArguments
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from torch.utils.data import Dataset

    tokenizer = AutoTokenizer.from_pretrained(
        model_id, revision=revision, trust_remote_code=False)
    tokenizer.pad_token = tokenizer.eos_token
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quant = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision, trust_remote_code=False,
        quantization_config=quant, device_map="auto")
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        bias="none", task_type="CAUSAL_LM"))
    eos = tokenizer.eos_token_id

    class ChatDataset(Dataset):
        def __init__(self, filename: Path):
            self.rows = []
            for line in filename.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)["messages"]
                prompt_text = tokenizer.apply_chat_template(
                    item[:2], tokenize=False, add_generation_prompt=True)
                prefix = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
                suffix = tokenizer(
                    item[2]["content"], add_special_tokens=False)["input_ids"] + [eos]
                if not prefix or len(prefix) > 1024 or not suffix or len(suffix) > 512:
                    raise TrainingBlocked("sample exceeds bounded context budget")
                self.rows.append({
                    "input_ids": prefix + suffix,
                    "labels": [-100] * len(prefix) + suffix
                })

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, index):
            return self.rows[index]

    def collate(batch):
        n = max(len(x["input_ids"]) for x in batch)
        return {
            "input_ids": torch.tensor([
                x["input_ids"] + [tokenizer.pad_token_id] * (n - len(x["input_ids"]))
                for x in batch], dtype=torch.long),
            "attention_mask": torch.tensor([
                [1] * len(x["input_ids"]) + [0] * (n - len(x["input_ids"]))
                for x in batch], dtype=torch.long),
            "labels": torch.tensor([
                x["labels"] + [-100] * (n - len(x["labels"]))
                for x in batch], dtype=torch.long),
        }

    train_ds = ChatDataset(Path(dataset) / "train.jsonl")
    eval_ds = ChatDataset(Path(dataset) / "holdout.jsonl")
    args = TrainingArguments(
        output_dir=str(output), max_steps=max_steps,
        per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=1e-4, warmup_ratio=0.05,
        logging_steps=10, save_steps=100, save_total_limit=2,
        eval_strategy="steps", eval_steps=100,
        bf16=(dtype == torch.bfloat16), fp16=(dtype == torch.float16),
        gradient_checkpointing=True, report_to=[],
        push_to_hub=False, remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model, args=args, train_dataset=train_ds,
        eval_dataset=eval_ds, data_collator=collate)
    trainer.train()
    target = Path(output)
    trainer.save_model(str(target / "adapter"))
    tokenizer.save_pretrained(str(target / "adapter"))
    (target / "provenance.json").write_text(json.dumps({
        "status": "ADAPTER_TRAINED_NOT_PROMOTED",
        "model": model_id, "revision": revision, "max_steps": max_steps,
        "dataset": metadata,
        "warning": "Must pass independent withheld test suite before deployment."
    }, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--dataset", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--revision", required=True)
    cli.add_argument("--max-steps", type=int, default=120)
    args = cli.parse_args()
    try:
        run_training(args.dataset, args.output, args.revision,
                     max_steps=args.max_steps)
        return 0
    except (TrainingBlocked, OSError, ValueError, KeyError, TypeError) as exc:
        print("TRAINING BLOCKED:", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
