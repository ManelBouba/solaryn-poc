"""Isolated execution of the existing pilot, never a substitute physics engine."""
from pathlib import Path
import sys
import json
import hashlib
from datetime import datetime, timezone

PILOT = Path(__file__).resolve().parents[1] / "Solaryn_Pilot"
sys.path.insert(0, str(PILOT))
import numpy as np
import pandas as pd
from src.pilot_service import analyze
from src.module_offer_io import load_module_offer_csv
from src.outdoor_validation import validate_iec61853_pmax_layer
from src.run_store import json_bytes, sha, RunStore
from src.procurement_model import Project, Candidate, compare
from decision_chain import decision_chain


def ac_from_dc(dc, weights, dc_ac_ratio, efficiency, availability, curtailment):
    dc, weights = np.asarray(dc, float), np.asarray(weights, float)
    if dc.shape != weights.shape or not np.isfinite(dc).all() or not np.isfinite(weights).all() or (dc < 0).any() or (weights <= 0).any():
        raise ValueError("Invalid hourly DC power or integration weights")
    for value, low, high in [(dc_ac_ratio,.5,3),(efficiency,.5,1),(availability,.01,1),(curtailment,0,.99)]:
        if not np.isfinite(value) or not low <= value <= high:
            raise ValueError("Invalid AC conversion assumption")
    preclip = dc * efficiency
    clipped = np.minimum(preclip, 1 / dc_ac_ratio)
    net = clipped * availability * (1-curtailment)
    return net, {"dc_kwh_kwp":float(np.sum(dc*weights)),
                 "conversion_loss_kwh_kwp":float(np.sum((dc-preclip)*weights)),
                 "clipping_loss_kwh_kwp":float(np.sum((preclip-clipped)*weights)),
                 "availability_curtailment_loss_kwh_kwp":float(np.sum((clipped-net)*weights)),
                 "net_ac_kwh_kwp":float(np.sum(net*weights))}


def measured_validation():
    source = PILOT / "validation/external/iea_pvps_task13_supsi_csi"
    matrix = source / "IEA_PVPS_TASK13_SUPSI_cSi_IEC61853_Pmax.csv"
    summary, monthly, points = validate_iec61853_pmax_layer(source / "data", matrix)
    summary.update(mae_w=float(points.error_w.abs().mean()),
                   max_absolute_residual_w=float(points.error_w.abs().max()),
                   nearest_fallback_fraction_pct=100*summary["nearest_fallback_rows"]/summary["retained_rows"],
                   input_hashes={p.relative_to(source).as_posix():sha(p.read_bytes()) for p in [matrix,*sorted((source/'data').glob('*.csv'))]},
                   executed_at=datetime.now(timezone.utc).isoformat(),
                   scope="Independent supplied characterization versus outdoor measurements; reference electrical interpolation only.",
                   does_not_validate=["commercial SKU ranking","climate resource","thermal model","rear irradiance","AC conversion","degradation","economics","bankability"])
    # The inherited routine labels every completed calculation PASS. Do not
    # reinterpret that label as an engineering acceptance criterion.
    summary['inherited_status']=summary['status']
    reference=json.loads((PILOT/'validation/results/measured_replay.json').read_text(encoding='utf-8'))
    metrics=['rmse_w','rmse_pct_stc','mbe_w','r2','mae_w']
    reproduced=(summary['input_hashes']==reference['input_hashes']
                and summary['retained_rows']==reference['retained_rows']
                and all(np.isfinite(summary[k]) and abs(summary[k]-reference[k])<=1e-5 for k in metrics))
    if not reproduced:
        raise ValueError('Measured electrical benchmark changed: reference inputs or metrics no longer reproduce')
    summary['status']='REFERENCE_BENCHMARK_REPRODUCED'
    summary['acceptance_policy']='Regression: identical source hashes/row count; metrics absolute tolerance 1e-5. No general scientific acceptance threshold defined.'
    summary['monthly']=monthly.to_dict('records')
    sampled=points.iloc[::max(1,int(np.ceil(len(points)/300)))].copy()
    summary['comparison_points']=sampled[['Pm','predicted_pmax_w','error_w']].to_dict('records')
    summary['plot_sampling']='At most 300 evenly spaced retained records for display; all retained observations used for metrics.'
    return summary, monthly


def execute(request, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    params, configuration = request["project"], request["configuration"]
    lat, lon = request["latitude"], request["longitude"]
    if configuration["weather_source"] == "riyadh_reference":
        if abs(lat-24.7136)>.001 or abs(lon-46.6753)>.001:
            raise ValueError("The recorded Riyadh resource requires coordinates 24.7136, 46.6753. Use Live NASA for other sites.")
        path = PILOT / "data/reference/riyadh_hourly.csv"
        metadata=json.loads((PILOT/'data/reference/riyadh_weather.json').read_text(encoding='utf-8'))
        if sha(path.read_bytes())!=metadata['sha256']:
            raise ValueError('Recorded climate source checksum mismatch')
        weather = pd.read_csv(path, parse_dates=["time_utc"])
        weather.attrs.update(**metadata.get('metadata',{}),source="Saved NASA POWER Riyadh 2020",source_sha256=sha(path.read_bytes()),retrieved_utc=metadata['retrieved_utc'])
    else:
        from src.data_fetchers import fetch_nasa_power_hourly_dataframe
        year = configuration["weather_year"]
        weather = fetch_nasa_power_hourly_dataframe(lat,lon,f"{year}-01-01",f"{year}-12-31",time_standard="UTC")
        weather.attrs["time_standard"]="UTC"
    catalog=load_module_offer_csv(PILOT/'data/raw/module_candidate_master.csv')
    identifiers=configuration["module_ids"]
    if len(set(identifiers))!=len(identifiers) or not 2<=len(identifiers)<=5:
        raise ValueError("Select 2–5 distinct exact modules")
    if not set(identifiers).issubset(set(catalog.module_id)):
        raise ValueError("Unknown exact module identifier")
    modules=catalog[catalog.module_id.isin(identifiers)].copy()
    validated, monthly_validation=measured_validation()
    source=PILOT/'validation/external/iea_pvps_task13_supsi_csi'
    for relative, checksum in validated['input_hashes'].items():
        original=source/relative
        data=original.read_bytes()
        if sha(data)!=checksum: raise ValueError('Measured validation source changed during execution')
        destination=folder/'validation-inputs'/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)
    project=dict(project_name=params["name"],latitude=lat,longitude=lon,
                 system_size_mw=params["capacity_mwp"],target_lifetime_years=params["years"],currency="EUR",
                 tilt_deg=configuration["tilt_deg"],azimuth_deg=configuration["azimuth_deg"],
                 soiling_loss_pct=configuration["soiling_pct"],common_degradation_pct_year=configuration["degradation"]*100,
                 row_geometry_enabled=configuration["row_geometry"],albedo=configuration["albedo"],
                 gcr=configuration["gcr"],row_height_m=configuration["height_m"],row_pitch_m=configuration["pitch_m"],
                 salinity_stress=configuration.get("salinity_stress","auto"),
                 hard_qualification_gates=configuration.get("hard_qualification_gates",False),
                 snow_model_enabled=configuration.get("snow_model_enabled",True))
    result=analyze(PILOT,project,modules,weather,store_root=folder/'pilot')
    # Do not elevate the original gate based on a cached report alone.
    result["reference_validation"]=validated
    result["validation_gates"]["reference_iec_electrical_layer"]="REPLAY_COMPLETED_SCOPED"
    if result["status"]!="completed" or any(c["simulation_status"]!="completed" for c in result["candidates"]):
        raise ValueError("A selected module failed its physical simulation; no economic ranking generated")
    hourly=pd.read_csv(folder/'pilot'/result['run_id']/'Hourly-physics.csv')
    energy, ac_frames, candidates=[], [], []
    for mid in identifiers:
        frame=hourly[hourly.module_id==mid].copy()
        net, losses=ac_from_dc(frame.specific_power_kw_per_kwp,frame.days_weight,
            configuration['dc_ac_ratio'],configuration['inverter_efficiency'],configuration['availability'],configuration['curtailment'])
        row=next(c for c in result['candidates'] if c['module_id']==mid)
        if not np.isclose(losses['dc_kwh_kwp'],row['metrics']['annual_yield_kwh_kwp'],rtol=1e-9):
            raise ValueError("Hourly-to-annual DC energy reconciliation failed")
        frame['net_ac_kw_kwp']=net
        frame['net_ac_energy_kwh_kwp']=net*frame.days_weight
        frame['month']=pd.to_datetime(frame.timestamp,utc=True).dt.month
        ac_frames.append(frame)
        energy.append({"module_id":mid,"model":row['model'],**losses,
                       "monthly_ac":frame.groupby('month').net_ac_energy_kwh_kwp.sum().to_dict()})
        quote=configuration['quotes_eur_w'].get(mid)
        if quote is not None:
            candidates.append(Candidate(name=mid,model=row['model'],bom="Unknown",quote_eur_w=quote,
                net_ac_kwh_kwp=losses['net_ac_kwh_kwp'],yield_source="Physics run "+result['run_id'],
                degradation=configuration['degradation'],event_year=min(15,params['years'])))
    economics=None
    if len(candidates)==len(identifiers):
        economics=compare(Project(**params),candidates)
        economics['status']='Exploratory physics-derived economics — not procurement approval'
    pd.concat(ac_frames).to_csv(folder/'Hourly-DC-AC.csv',index=False)
    monthly_validation.to_csv(folder/'Measured-validation-monthly.csv',index=False)
    output={"schema_version":"physics-platform-1.0","project":request,"physics":result,
            "measured_validation":validated,"ac_energy":energy,"economics":economics,
            "ac_model":{"formula":"P_AC=min(P_DC*eta,1/DCAC)*availability*(1-curtailment)",
                        "scope":"Constant-efficiency, hourly clipping approximation. Not an independently validated inverter or plant AC model.",
                        "soiling":"Already applied inside the DC model; not applied twice."},
            "decision_scope":"Physical and economic outputs remain conditional on the original evidence gates. No automatic approval.",
            "created_at":datetime.now(timezone.utc).isoformat()}
    output['decision_chain']=decision_chain(params,configuration,energy,weather,result,economics)
    for original in (PILOT/'src').glob('*.py'):
        destination=folder/'model-source'/original.name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(original.read_bytes())
    (folder/'Result.json').write_bytes(json_bytes(output))
    files=[p for p in folder.rglob('*') if p.is_file() and p.name!='Manifest-platform.json']
    (folder/'Manifest-platform.json').write_bytes(json_bytes({p.relative_to(folder).as_posix():sha(p.read_bytes()) for p in files}))
    return output


if __name__=='__main__':
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    execute(request,Path(sys.argv[2]))
