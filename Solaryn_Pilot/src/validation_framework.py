from __future__ import annotations
import numpy as np
import pandas as pd


def error_metrics(measured, predicted) -> dict:
    y=np.asarray(measured,dtype=float); p=np.asarray(predicted,dtype=float)
    mask=np.isfinite(y)&np.isfinite(p); y=y[mask]; p=p[mask]
    if not len(y): return {'n':0,'rmse':np.nan,'mae':np.nan,'mbe':np.nan,'nrmse_pct':np.nan,'mape_pct':np.nan}
    e=p-y; mean_abs=max(abs(y.mean()),1e-9)
    return {'n':int(len(y)),'rmse':float(np.sqrt(np.mean(e**2))),'mae':float(np.mean(abs(e))),
            'mbe':float(np.mean(e)),'nrmse_pct':float(np.sqrt(np.mean(e**2))/mean_abs*100),
            'mape_pct':float(np.mean(abs(e)/np.maximum(abs(y),1e-9))*100)}

def ranking_metrics(measured_scores: dict[str,float], predicted_scores: dict[str,float]) -> dict:
    common=[k for k in measured_scores if k in predicted_scores]
    if len(common)<2: return {'winner_match':False,'pairwise_accuracy_pct':np.nan,'pairwise_correct':0,'pairwise_total':0}
    mw=max(common,key=lambda k: measured_scores[k]); pw=max(common,key=lambda k: predicted_scores[k])
    correct=total=0
    for i,a in enumerate(common):
        for b in common[i+1:]:
            md=np.sign(measured_scores[a]-measured_scores[b]); pdif=np.sign(predicted_scores[a]-predicted_scores[b])
            if md==pdif: correct+=1
            total+=1
    return {'measured_winner':mw,'predicted_winner':pw,'winner_match':mw==pw,
            'pairwise_correct':correct,'pairwise_total':total,'pairwise_accuracy_pct':100*correct/max(total,1)}

def layer_validation_report(layers: dict[str,tuple]) -> pd.DataFrame:
    rows=[]
    for name,(measured,predicted) in layers.items(): rows.append({'layer':name,**error_metrics(measured,predicted)})
    return pd.DataFrame(rows)
