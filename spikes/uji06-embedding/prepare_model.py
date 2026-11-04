"""Download multilingual-e5-small ONNX files (fp32 + official int8) and write MODEL_INFO.json.

Uses only the standard library. No torch / transformers needed because the
official repo ships ONNX files (brief section 5, step 1-2).

Usage: python prepare_model.py [--out C:/nibras-staging/models]
"""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

REPO = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
FILES = {
    "model_fp32.onnx": "onnx/model.onnx",
    "model_int8.onnx": "onnx/model_qint8_avx512_vnni.onnx",
    "tokenizer.json": "onnx/tokenizer.json",
    "tokenizer_config.json": "onnx/tokenizer_config.json",
    "special_tokens_map.json": "onnx/special_tokens_map.json",
    "config.json": "onnx/config.json",
    "1_Pooling_config.json": "1_Pooling/config.json",
    "README_modelcard.md": "README.md",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="C:/nibras-staging/models")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    info_files = {}
    for local, remote in FILES.items():
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{remote}"
        dest = out / local
        if not dest.exists():
            print(f"download {url}")
            urllib.request.urlretrieve(url, dest)
        info_files[local] = {
            "source_url": url,
            "bytes": dest.stat().st_size,
            "sha256": sha256(dest),
        }

    card = (out / "README_modelcard.md").read_text(encoding="utf8", errors="replace")
    license_line = next((l for l in card.splitlines() if l.lower().startswith("license:")), "license: (not found)")
    info = {
        "repo": REPO,
        "revision": REVISION,
        "license_from_model_card": license_line.split(":", 1)[1].strip(),
        "license_note": "Verified from YAML front matter of the model card at the pinned revision.",
        "int8_variant": "Official file onnx/model_qint8_avx512_vnni.onnx from the model repo; not self-quantized.",
        "fp32_variant": "Official file onnx/model.onnx from the model repo.",
        "files": info_files,
    }
    (out / "MODEL_INFO.json").write_text(json.dumps(info, indent=2), encoding="utf8")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
