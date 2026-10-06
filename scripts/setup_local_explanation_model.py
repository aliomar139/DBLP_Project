"""Download one pinned CPU-quantized local instruction model for evaluation only."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.work/rag-benchmark/packages'))

from huggingface_hub import snapshot_download

REPOSITORY = 'microsoft/Phi-3-mini-4k-instruct-onnx'
REVISION = 'c22ed26f128799a5b52d72b8d8fa80c0a095af09'
INCLUDE = 'cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4/*'
DESTINATION = ROOT / '.work/llm-benchmark/models/phi-3-mini-cpu-int4'
MODEL_DIRECTORY = DESTINATION / 'cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4'
MANIFEST = ROOT / 'reports/assistant/local-model-phi3-int4-setup-v1.json'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    snapshot_download(repo_id=REPOSITORY, revision=REVISION,
                      allow_patterns=[INCLUDE], local_dir=str(DESTINATION))
    files = sorted(path for path in MODEL_DIRECTORY.rglob('*') if path.is_file())
    if not files:
        raise RuntimeError('The pinned model snapshot did not contain the requested CPU files')
    genai_config = MODEL_DIRECTORY / 'genai_config.json'
    if not genai_config.is_file():
        raise RuntimeError('The pinned model is missing ONNX Runtime GenAI configuration')
    report = {
        'version': 1,
        'status': 'downloaded_for_local_benchmark_only',
        'repository': REPOSITORY,
        'revision': REVISION,
        'quantization': 'INT4 RTN block 32, CPU acc-level-4',
        'model_directory': str(MODEL_DIRECTORY.relative_to(ROOT)),
        'downloaded_at_utc': datetime.now(timezone.utc).isoformat(),
        'files': [{'path': str(path.relative_to(DESTINATION)),
                   'bytes': path.stat().st_size, 'sha256': sha256(path)} for path in files],
        'total_bytes': sum(path.stat().st_size for path in files),
        'activation': 'not selected; benchmark candidate only',
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in
                      ('status', 'repository', 'revision', 'model_directory', 'total_bytes')}, indent=2))


if __name__ == '__main__':
    main()
