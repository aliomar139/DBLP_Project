"""One-time, pinned local model download. Does not send corpus data or questions."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".work/rag-benchmark/packages"))
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_XET"] = "1"
from huggingface_hub import HfApi, hf_hub_download

REPO = "sentence-transformers/all-MiniLM-L6-v2"
MODEL = ROOT / ".work/rag-benchmark/model"


def main():
    MODEL.mkdir(parents=True, exist_ok=True)
    # Pin the resolved commit before downloading every component.
    revision = HfApi().model_info(REPO).sha
    files = ["onnx/model_quint8_avx2.onnx", "tokenizer.json", "tokenizer_config.json",
             "config.json", "sentence_bert_config.json", "1_Pooling/config.json", "README.md"]
    hashes = {}
    for name in files:
        path = Path(hf_hub_download(REPO, name, revision=revision, local_dir=MODEL))
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"Downloaded {name}: {path.stat().st_size} bytes", flush=True)
    manifest = {"repository": REPO, "revision": revision, "sha256": hashes,
                "purpose": "local offline embedding feasibility benchmark and versioned candidate-index construction"}
    (MODEL / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
