"""Copy the participant-pack data into the repo and write a SHA-256 manifest.

Stdlib only. Run from anywhere: all paths resolve from this file, not the working directory.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
PACK = REPO / "bhopal-impact-lab-2026-problem-statements-main" / "track-1-bhumi-vikas-sahayak"

SOURCE_DIR = BACKEND / "data" / "source"
PDF_DIR = REPO / "web" / "public" / "pdf"

DATA_FILES = [
    "bhumi_vikas_rules.jsonl",
    "bhumi_vikas_rules_fulltext_by_page.txt",
    "DATA_DICTIONARY.md",
]
PDFS = {
    "MP_Bhumi_Vikas_Rules_2012_upto_2025-03-06_EN.pdf": "rules-en.pdf",
    "MP_Bhumi_Vikas_Rules_2012_upto_2025-03-06_HI.pdf": "rules-hi.pdf",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def copy(src: Path, dst: Path) -> Path:
    if not src.is_file():
        sys.exit(f"missing source file: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"copied {src.name} -> {dst.relative_to(REPO)}")
    return dst


def main() -> None:
    manifest: dict[str, str] = {}

    for name in DATA_FILES:
        dst = copy(PACK / "data" / name, SOURCE_DIR / name)
        manifest[name] = sha256(dst)

    for src_name, dst_name in PDFS.items():
        dst = copy(PACK / "resources" / src_name, PDF_DIR / dst_name)
        manifest[f"pdf/{dst_name}"] = sha256(dst)

    (SOURCE_DIR / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {(SOURCE_DIR / 'MANIFEST.json').relative_to(REPO)}")

    playbook = REPO / "Impact_Lab_Cerebras_Hackathon_Cheatsheet_v2.md"
    copy(playbook, REPO / "docs" / "PLAYBOOK.md")


if __name__ == "__main__":
    main()
