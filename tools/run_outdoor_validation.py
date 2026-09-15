from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.outdoor_validation import validate_iec61853_pmax_layer


DVP_ROOT = ROOT / "validation/external/iea_pvps_task13_supsi_csi"


def main() -> None:
    summary, monthly, points = validate_iec61853_pmax_layer(
        DVP_ROOT / "data",
        DVP_ROOT / "IEA_PVPS_TASK13_SUPSI_cSi_IEC61853_Pmax.csv",
    )
    outputs = ROOT / "outputs"
    outputs.mkdir(exist_ok=True)
    (outputs / "DVP_OUTDOOR_VALIDATION_SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    monthly.to_csv(outputs / "DVP_OUTDOOR_VALIDATION_MONTHLY.csv", index=False)
    points.to_csv(outputs / "DVP_OUTDOOR_VALIDATION_POINTS.csv", index=False)
    pd.DataFrame([summary]).to_csv(ROOT / "MEASURED_VALIDATION_RESULTS.csv", index=False)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
