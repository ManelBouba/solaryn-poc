from __future__ import annotations

import difflib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT.parent / "SOLARYN_POC_FINAL_VALIDATION_V9_2_1_FIXED (1).zip"
OUTPUT = ROOT / "COMPLETE_CODE_DIFF.patch"

INCLUDE = [
    "ARCHITECTURE_MAP.md", "AUDIT_FINDINGS.md", "BASELINE_REPRODUCTION.md", "CHANGELOG.md",
    "FINAL_HARDENING_REPORT.md", "FINAL_VALIDATION_GATES.md",
    "UNRESOLVED_LIMITATIONS.md", "VALIDATION_PLAN.md",
    "requirements.txt", "requirements-lock.txt", "VALIDATION_STATUS.txt",
    "app/epc_module_mode.py", "app/streamlit_app.py", "src/benchmark_regression.py", "src/data_fetchers.py",
    "src/copilot_prompt.py", "src/epc_decision.py", "src/epc_report.py", "src/outdoor_validation.py",
    "src/module_iv_engine.py", "src/module_offer_io.py", "tests/test_bias_correction_v9.py",
    "tests/test_hourly_data_fetchers.py", "tests/test_module_offer_io.py",
    "tests/test_physics_sanity.py", "tests/test_poc_validation_mode.py",
    "tests/test_riyadh_benchmark_regression.py",
    "tests/test_ui_copy_and_states.py",
    "tests/test_outdoor_validation.py", "tools/run_outdoor_validation.py",
    "tools/generate_code_diff.py", "tools/generate_validation_artifacts.py",
    "tools/package_final.py", "tools/regenerate_manifest.py",
    "docs/EPC_SCIENCE_MODEL_CARD.md", "data/processed/riyadh_benchmark_v9_2_1.csv",
]


def baseline_text(archive: zipfile.ZipFile, relative: str) -> str:
    name = f"SOLARYN_POC_FINAL_VALIDATION/{relative}"
    try:
        return archive.read(name).decode("utf-8")
    except KeyError:
        return ""


def main() -> None:
    chunks = []
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for relative in INCLUDE:
            current_path = ROOT / relative
            before = baseline_text(archive, relative)
            after = current_path.read_text(encoding="utf-8") if current_path.exists() else ""
            if before == after:
                continue
            chunks.extend(difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            ))
    OUTPUT.write_text("".join(chunks), encoding="utf-8")


if __name__ == "__main__":
    main()
