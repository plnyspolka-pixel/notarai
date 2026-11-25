"""Pobieranie wyłącznie publicznych wag podczas budowania obrazu, bez spraw."""
import argparse
from pathlib import Path

MODEL_ID = "radlab/pii-pl-v1.0"
REVISION = "97ba763518491bb17dc10ab1870453d3abb4ef09"
PLIKI = ["config.json", "model.safetensors", "tokenizer.json",
         "tokenizer_config.json", "special_tokens_map.json", "README.md",
         "id2label.json", "label2id.json"]


def main():
    from huggingface_hub import snapshot_download
    p = argparse.ArgumentParser()
    p.add_argument("katalog")
    args = p.parse_args()
    path = Path(args.katalog)
    snapshot_download(repo_id=MODEL_ID, revision=REVISION, local_dir=str(path),
                      allow_patterns=PLIKI, token=False)
    for nazwa in PLIKI:
        if not (path / nazwa).is_file():
            raise RuntimeError("Missing model artifact: " + nazwa)
    # Nie wolno pobierać ani ładować pickle, training_args.bin czy kodu modelu.
    if any(p.suffix in (".bin", ".pkl", ".py", ".pt", ".pth") for p in path.iterdir()):
        raise RuntimeError("Unexpected executable/pickle artifact")
    (path / "notarai-revision.txt").write_text(REVISION + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
