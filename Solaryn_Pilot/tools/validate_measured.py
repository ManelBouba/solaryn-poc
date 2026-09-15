"""Re-execute the supplied measured electrical validation; publish scoped metrics."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from src.outdoor_validation import validate_iec61853_pmax_layer
from src.run_store import json_bytes,sha

def main():
    source=ROOT/'validation/external/iea_pvps_task13_supsi_csi'
    matrix=source/'IEA_PVPS_TASK13_SUPSI_cSi_IEC61853_Pmax.csv'
    summary,monthly,points=validate_iec61853_pmax_layer(source/'data',matrix)
    error=points.error_w.to_numpy(float)
    summary.update(mae_w=float(np.abs(error).mean()),max_absolute_residual_w=float(np.abs(error).max()),
        interpolation_fraction_pct=100*(1-summary['nearest_fallback_rows']/summary['retained_rows']),
        nearest_fallback_fraction_pct=100*summary['nearest_fallback_rows']/summary['retained_rows'],
        input_hashes={p.relative_to(source).as_posix():sha(p.read_bytes()) for p in [matrix,*sorted((source/'data').glob('*.csv'))]},
        validation_design='Independent supplied characterization matrix versus measured outdoor observations; no fitting to outdoor holdout.',
        gate_scope='reference measured electrical interpolation only; commercial SKU and full recommendation gates remain PENDING')
    output=ROOT/'validation/results';output.mkdir(parents=True,exist_ok=True)
    (output/'measured_replay.json').write_bytes(json_bytes(summary))
    monthly.to_csv(output/'measured_replay_monthly.csv',index=False)
    print(json_bytes(summary).decode())

if __name__=='__main__': main()
