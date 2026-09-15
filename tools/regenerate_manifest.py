from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "FILE_MANIFEST_SHA256.txt"
EXCLUDED_DIRS = {".venv", "__pycache__", ".pytest_cache"}
EXCLUDED_NAMES = {"FILE_MANIFEST_SHA256.txt", ".coverage"}


def packaged_files():
    for path in sorted(ROOT.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix.lower() in {".pyc", ".zip"}:
            continue
        yield path, relative


def main() -> None:
    lines = []
    for path, relative in packaged_files():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  ./{relative.as_posix()}\n")
    MANIFEST.write_text("".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
