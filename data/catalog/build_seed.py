"""Reproducible catalog transcription. No runtime downloads or model inference.

The historical Pilot CSV is a migration input only; application reads the output.
JSON-formatted YAML sidecars are valid YAML 1.2 and readable without PyYAML.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKED = '2026-09-15'
rows = []
sources = {}
families = ['PERC','TOPCon','HJT / SHJ','CdTe','HPBC','IBC','TOPCon Bifacial','HJT Bifacial','TOPCon Bifacial','TOPCon Bifacial']
current = {
    2: 'https://www.recgroup.com/en/downloads/product-downloads/information-sheet-rec-alpha-pure-rx',
    3: 'https://www.firstsolar.com/Products/Series-7',
    4: 'https://eu.longi.com/nl/longi-solar-panels-datasheets/lr7-72hvh-655-670',
    6: 'https://www.canadiansolar.com/na/downloads',
    7: 'https://www.canadiansolar.com/na/downloads',
}
def num(v):
    return float(v) if v and v.lower() not in ('unknown','null') else None

def add(r, listing=None, note=None):
    r.setdefault('source_checked_at', CHECKED)
    r.setdefault('commercial_status','UNKNOWN')
    r.setdefault('decision_eligibility','SCREENING_ONLY')
    r.setdefault('evidence_level','C_MANUFACTURER_DATASHEET')
    for field in ('iec61853_available','iam_available','spectral_response_available','thermal_data_available','independent_field_data_available'):
        r.setdefault(field, None)
    r.setdefault('source_note', note or 'Manufacturer datasheet. No reviewed module-specific electrical surface in this release.')
    sources[r['module_id']] = {'datasheet_url':r['datasheet_url'],'datasheet_revision':r.get('datasheet_revision'),
        'source_checked_at':CHECKED,'current_listing_url':listing,'verification_note':note or r['source_note'],
        'availability_policy':'Current official listing is marketing evidence, not stock, price or a procurement guarantee.',
        'electrical_evidence':None}
    rows.append(r)

with (ROOT/'Solaryn_Pilot/data/raw/module_candidate_master.csv').open(encoding='utf-8-sig',newline='') as f:
    for i, old in enumerate(csv.DictReader(f)):
        r = {'module_id':old['module_id'],'manufacturer':old['manufacturer'],'model':old['model'],
             'technology_family':families[i],'technology_subtype':old['technology_label'],
             'cell_architecture':old['technology_label'],'module_architecture':old['glass_structure'],
             'monofacial_or_bifacial':'BIFACIAL' if i in (6,7,8,9) else 'MONOFACIAL',
             'commercial_status':'COMMERCIAL' if i in current else 'UNKNOWN',
             'application':'ROOFTOP|UTILITY' if i not in (2,3,5) else ('UTILITY' if i==3 else 'ROOFTOP'),
             'market_regions':None,'datasheet_url':old['source_url'],'datasheet_revision':old['revision_date'] or None,
             'glass_structure':old['glass_structure'], 'warranty_years':num(old['warranty_years']),
             'warranted_degradation_text':old['source_note'],'source_note':old['source_note']}
        for dest, src in {'pmax_w':'pmax_w','vmp_v':'vmp_v','imp_a':'imp_a','voc_v':'voc_v','isc_a':'isc_a',
                          'efficiency_pct':'module_efficiency_pct','gamma_pmp_pct_per_c':'gamma_pmax_pct_c',
                          'alpha_isc_pct_per_c':'alpha_isc_pct_c','beta_voc_pct_per_c':'beta_voc_pct_c','module_area_m2':'module_area_m2'}.items():
            r[dest]=num(old[src])
        r['bifaciality_pct']=num(old.get('bifaciality_factor'))*100 if old.get('bifaciality_source') and num(old.get('bifaciality_factor')) is not None else None
        if i==3:
            r.update(model='FS-7530A-TR1',market_regions='US',datasheet_revision='MPD-00903-07-US JUL 2024',
                     datasheet_url='https://www.firstsolar.com/-/media/First-Solar/Technical-Documents/Series-7/Series-7-TR1-High-Bin-Datasheet.pdf',
                     vmp_v=186.9,imp_a=2.84,voc_v=226.7,isc_a=3.05,efficiency_pct=19.0,module_area_m2=2.80)
        if i==2:r['datasheet_revision']='IEC EN AUCEC 101125'
        if i==4:r['datasheet_revision']='Scientist BGV02 20250313 EN'
        if i==6:r.update(datasheet_revision='v1.1 F68 L1B TX',market_regions='US')
        if i==7:r.update(datasheet_revision='v1.4C1 F68 L1 TX90',market_regions='US')
        add(r,current.get(i), 'Electrical values migrated from the audited Pilot datasheet row. '+('Exact series/power range appears in the linked current official listing; verify regional quote and variant before procurement.' if i in current else 'Old exact SKU datasheet retained. Current availability/revision not independently established; UNKNOWN is intentional.'))

aiko='https://aikosolar.com/wp-content/uploads/2026/03/Neostar-3SPlus60_193-AIKO-A-MCE60Db_530-550W-1954x1134x30mm_202602_V4.1_ANZ.pdf'
for p, voc, vmp, isc, imp, eff in [(530,45.40,38.20,14.76,13.88,23.9),(535,45.50,38.30,14.80,13.97,24.1),(540,45.60,38.40,14.84,14.07,24.4),(545,45.70,38.50,14.88,14.16,24.6),(550,45.80,38.60,14.92,14.25,24.8)]:
    add(dict(module_id=f'MOD_ABC_AIKO_A{p}_MCE60DB',manufacturer='AIKO',model=f'AIKO-A{p}-MCE60Db',technology_family='ABC',technology_subtype='N-type ABC',cell_architecture='All back contact',module_architecture='Bifacial dual glass',monofacial_or_bifacial='BIFACIAL',commercial_status='COMMERCIAL',application='ROOFTOP',market_regions='AU|NZ',datasheet_url=aiko,datasheet_revision='202602 V4.1 ANZ',pmax_w=p,vmp_v=vmp,imp_a=imp,voc_v=voc,isc_a=isc,efficiency_pct=eff,gamma_pmp_pct_per_c=-.26,alpha_isc_pct_per_c=.05,beta_voc_pct_per_c=-.22,bifaciality_pct=40,module_area_m2=1.954*1.134,glass_structure='2.0 mm + 2.0 mm glass',warranty_years=30,warranted_degradation_text='At most 1% year 1; at most 0.35% annually thereafter. Warranty only, not measured degradation.'),
        'https://aikosolar.com/au/products/neostar-3splus60-dual-glass/', 'Exact STC power-bin row and ANZ variant transcribed from official PDF page 2; current AU listing includes 530–550 W. Pmax bifaciality 40% ±5%; rear gain is not modeled.')

for p, eff, vmp, imp, voc, isc in [(440,22.8,40.5,10.87,48.2,11.58),(435,22.5,40.3,10.82,48.2,11.57),(425,22.0,39.8,10.68,48.1,11.55)]:
    add(dict(module_id=f'MOD_IBC_MAXEON_SPR_MAX6_{p}',manufacturer='Maxeon',model=f'SPR-MAX6-{p}',technology_family='IBC',technology_subtype='Maxeon Gen 6 IBC',cell_architecture='Interdigitated back contact',module_architecture='White backsheet / black frame',monofacial_or_bifacial='MONOFACIAL',commercial_status='COMMERCIAL',application='ROOFTOP',market_regions='US',datasheet_url='https://maxeon-production.squarespace.com/s/Maxeon-6-DC-425-440-W.pdf',datasheet_revision='552142 REV A / LTR_US March 2024',pmax_w=p,vmp_v=vmp,imp_a=imp,voc_v=voc,isc_a=isc,efficiency_pct=eff,gamma_pmp_pct_per_c=-.29,alpha_isc_pct_per_c=.057,beta_voc_pct_per_c=-.239,bifaciality_pct=None,module_area_m2=1.872*1.032,glass_structure='3.2 mm front glass / white backsheet',warranty_years=40,warranted_degradation_text='98% year 1, maximum 0.25% annual warranty degradation; 40 years requires eligible installer and registration, otherwise 25 years.'),
        'https://www.maxeon.com/maxeon-solar-panels','Official current Maxeon page links this exact US 425–440 W datasheet. Electrical values from page 2; warranty eligibility conditions preserved.')

for p,eff,voc,isc,imp in [(145,13.8,89.4,2.35,2.09),(150,14.2,89.5,2.41,2.16)]:
    add(dict(module_id=f'MOD_CIGS_AVANCIS_SKALA_{p}_B001_AU411',manufacturer='AVANCIS',model=f'SKALA {p} B001',technology_family='CIGS',technology_subtype='CIGS thin film',cell_architecture='CIGS thin film',module_architecture='Frameless facade with rear backrails',monofacial_or_bifacial='MONOFACIAL',commercial_status='UNKNOWN',application='BIPV_FACADE',market_regions='AU',datasheet_url='https://www.avancis.de/_Resources/Persistent/0/2/e/7/02e75f65598a8dd82cb3b909bb74a70ff14e97f8/FE_PD_SKALA_DATASHEET_AU_V4.11.pdf',datasheet_revision='Variant 4.11 Australia / February 2024',pmax_w=p,vmp_v=69.4,imp_a=imp,voc_v=voc,isc_a=isc,efficiency_pct=eff,gamma_pmp_pct_per_c=-.35,alpha_isc_pct_per_c=0,beta_voc_pct_per_c=-.26,bifaciality_pct=None,module_area_m2=1.587*.664,glass_structure='Glass-glass; 3 mm front glass',warranty_years=25,warranted_degradation_text='10-year product warranty. Minimum 90% at year 10 and 80% at year 25; not measured degradation.'),
        'https://www.avancis.de/en/downloads','Official PDF page 2 maps black B001 to 145/150 W. Facade application only. SKALA family is marketed; current availability of this exact AU 4.11 variant remains UNKNOWN pending manufacturer confirmation.')

checks_file=HERE/'source_http_checks.json'
if checks_file.exists():
    checks={r['url']:r for r in json.loads(checks_file.read_text(encoding='utf-8'))['checks']}
    for source in sources.values():
        check=checks.get(source['datasheet_url'])
        source['retrieval_check']=check
        if check and not check.get('pdf'):
            source['verification_note']+=' Retrieval on 2026-09-15 was unsuccessful; historical transcription retained, not newly reverified.'

headers=list(dict.fromkeys(k for r in rows for k in r))
with (HERE/'commercial_modules.csv').open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(rows)
(HERE/'commercial_module_sources.yaml').write_text(json.dumps({'version':'commercial-2026.09.15-1','modules':sources},indent=2,ensure_ascii=False),encoding='utf-8')
groups=[{'name':n,'decision_status':'SKU_EVIDENCE_REQUIRED'} for n in dict.fromkeys(r['technology_family'] for r in rows)]
groups.append({'name':'Perovskite–silicon tandem','commercial_status':'LIMITED_COMMERCIAL','decision_status':'EVIDENCE_GATED','source_url':'https://www.oxfordpv.com/intersolar-2026','note':'No verified exact procurable SKU and electrical inputs in this release. No selectable placeholder.'})
(HERE/'technology_families.yaml').write_text(json.dumps({'version':'taxonomy-1','groups':groups},indent=2,ensure_ascii=False),encoding='utf-8')
print(f'{len(rows)} exact records; {sum(r["commercial_status"]=="COMMERCIAL" for r in rows)} current listed; {len(groups)} browser groups')
