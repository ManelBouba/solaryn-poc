from pathlib import Path
import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
MATRIX = ROOT / 'IEA_PVPS_TASK13_SUPSI_cSi_IEC61853_Pmax.csv'

m = pd.read_csv(MATRIX)
points = m[['irradiance_w_m2','module_temperature_c']].to_numpy(float)
values = m['pmax_w'].to_numpy(float)
linear = LinearNDInterpolator(points, values, fill_value=np.nan)
nearest = NearestNDInterpolator(points, values)
gmin, gmax = m.irradiance_w_m2.min(), m.irradiance_w_m2.max()
tmin, tmax = m.module_temperature_c.min(), m.module_temperature_c.max()

frames=[]
for p in sorted(DATA.glob('*.csv')):
    d=pd.read_csv(p, sep=';')
    d.columns=[c.strip() for c in d.columns]
    d['source_file']=p.name
    frames.append(d)
df=pd.concat(frames, ignore_index=True)
df['timestamp']=pd.to_datetime(df['Date'].astype(str).str.strip()+' '+df['Time'].astype(str).str.strip(), dayfirst=True, errors='coerce')
for c in ['Pm','Voc','Isc','Tbom','Gpoa']:
    df[c]=pd.to_numeric(df[c], errors='coerce')
base=df.dropna(subset=['timestamp','Pm','Voc','Isc','Tbom','Gpoa']).copy()
physical=(base.Pm>=0)&(base.Voc>0)&(base.Isc>0)&(base.Gpoa>0)&(base.Pm<=base.Voc*base.Isc*1.000001)
v=base[physical & base.Gpoa.between(gmin,gmax) & base.Tbom.between(tmin,tmax)].copy()
query=np.column_stack([v.Gpoa.to_numpy(), v.Tbom.to_numpy()])
pred=np.asarray(linear(query),float)
hole=~np.isfinite(pred)
pred[hole]=np.asarray(nearest(query[hole]),float)
v['predicted_pmax_w']=pred
v['error_w']=v.predicted_pmax_w-v.Pm
rmse=float(np.sqrt(np.mean(v.error_w**2)))
mbe=float(v.error_w.mean())
stc=float(m.loc[(m.irradiance_w_m2==1000)&(m.module_temperature_c==25),'pmax_w'].iloc[0])
r2=float(1-np.sum(v.error_w**2)/np.sum((v.Pm-v.Pm.mean())**2))
bias=float((v.predicted_pmax_w.sum()/v.Pm.sum()-1)*100)
print('n =', len(v))
print('RMSE_W =', rmse)
print('RMSE_pct_STC =', 100*rmse/stc)
print('MBE_W =', mbe)
print('MBE_pct_STC =', 100*mbe/stc)
print('R2 =', r2)
print('cumulative_sampled_energy_bias_pct =', bias)
print('nearest_fallback_points =', int(hole.sum()))
