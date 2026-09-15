"""Generate a synthetic example or reproduce a downloaded decision JSON offline."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.procurement_model import Project, Candidate, compare, MODEL_VERSION
from src.procurement_store import report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Downloaded decision JSON to reproduce")
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "procurement")
    args = parser.parse_args()
    if args.input:
        saved = json.loads(args.input.read_text(encoding="utf-8"))
        if saved["model_version"] != MODEL_VERSION:
            raise ValueError("Saved model version differs; use the matching model release")
        result = compare(Project(**saved["project"]), [Candidate(**c) for c in saved["candidates"]],
                         saved["claims"], saved["scenario"]["degradation_add"], saved["scenario"]["yield_haircut"])
        if "climate_risks" in saved:
            result["climate_risks"] = saved["climate_risks"]
        if result != saved:
            raise ValueError("Recomputed result differs from the saved decision")
        print("Exact numerical replay passed")
    else:
        candidates = [Candidate("Candidate A", "Synthetic A", "Unknown", .11, 1850., "Synthetic example"),
                      Candidate("Candidate B", "Synthetic B", "Unknown", .13, 1880., "Synthetic example", degradation=.004)]
        result = compare(Project(), candidates)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decision.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    (args.output / "decision.md").write_text(report(result), encoding="utf-8")
    print(result["status"])
    print(args.output.resolve())


if __name__ == "__main__":
    main()
