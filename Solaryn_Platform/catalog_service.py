"""One versioned catalog, with unknown values preserved at the API boundary."""
import csv
import hashlib
import json
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1] / 'data/catalog'
FILES = ('commercial_modules.csv','commercial_module_sources.yaml','technology_families.yaml')
NUMERIC = {'pmax_w','vmp_v','imp_a','voc_v','isc_a','efficiency_pct','gamma_pmp_pct_per_c',
           'alpha_isc_pct_per_c','beta_voc_pct_per_c','bifaciality_pct','module_area_m2','warranty_years'}

def catalog():
    sources = json.loads((DIRECTORY/FILES[1]).read_text(encoding='utf-8'))
    records=[]
    with (DIRECTORY/FILES[0]).open(encoding='utf-8-sig',newline='') as f:
        for raw in csv.DictReader(f):
            row={k:(float(v) if k in NUMERIC else v) if v else None for k,v in raw.items()}
            for k in ('iec61853_available','iam_available','spectral_response_available','thermal_data_available','independent_field_data_available'):
                if row[k] is not None:row[k]=row[k].lower()=='true'
            source=sources['modules'][row['module_id']]
            row.update(technology=row['technology_subtype'],rated_power_w=row['pmax_w'],
                       temperature_coefficient_pct_per_c=row['gamma_pmp_pct_per_c'],
                       bifacial={'BIFACIAL':True,'MONOFACIAL':False}.get(row['monofacial_or_bifacial']),
                       evidence=row['evidence_level'],source_url=row['datasheet_url'],
                       source_note=source['verification_note'],source_provenance=source,
                       electrical_evidence=source.get('electrical_evidence'))
            records.append(row)
    checksum=hashlib.sha256(b''.join(name.encode()+b'\0'+(DIRECTORY/name).read_bytes() for name in FILES)).hexdigest()
    return {'modules':records,'release':sources['version']+'+'+checksum,'source':'data/catalog/commercial_modules.csv',
            'warning':'Official source records; marketed products require a regional quote. UNKNOWN means exact current availability is unconfirmed. All seeded models are screening only; rear-side generation is excluded.'}

def families():
    return json.loads((DIRECTORY/FILES[2]).read_text(encoding='utf-8'))['groups']
