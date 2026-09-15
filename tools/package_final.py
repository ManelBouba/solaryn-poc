from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

from regenerate_manifest import ROOT, MANIFEST, packaged_files


OUTPUT = ROOT / "SOLARYN_V9_2_1_FINAL_HARDENED.zip"


def main() -> None:
    if OUTPUT.exists():
        OUTPUT.unlink()
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(MANIFEST, MANIFEST.name)
        for path, relative in packaged_files():
            archive.write(path, relative.as_posix())

    with zipfile.ZipFile(OUTPUT) as archive:
        manifest_lines = archive.read(MANIFEST.name).decode("utf-8").splitlines()
        for line in manifest_lines:
            expected, relative = line.split("  ./", 1)
            actual = hashlib.sha256(archive.read(relative)).hexdigest()
            if actual != expected:
                raise RuntimeError(f"Packaged hash mismatch: {relative}")
    print(f"VERIFIED {len(manifest_lines)} packaged hashes: {OUTPUT}")


if __name__ == "__main__":
    main()
