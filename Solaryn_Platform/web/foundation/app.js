import { api } from './api.js';
import { SolarynLogo } from './logo.js';

const root = document.querySelector('#app');
const pages = [['site', '01', 'Site selection'], ['conditions', '02', 'Site conditions'], ['candidates', '03', 'Candidates'], ['processing', '04', 'Analysis'], ['results', '05', 'Results'], ['evidence', '06', 'Evidence']];
let site = null, climate = null, catalog = null, families = [], analysis = null, map = null, marker = null;
let selected = new Set(), filters = {}, generation = 0;
const climateRequests = new Map();
const fmt = n => n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 1 });
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const value = v => v == null ? '—' : esc(v);
const coords = s => s ? `${s.latitude}°, ${s.longitude}°` : 'No site selected';
const route = () => location.pathname.slice(1);
const readKey = key => { try { return sessionStorage.getItem(key); } catch { return null; } };
const writeKey = (key, val) => { try { val ? sessionStorage.setItem(key, val) : sessionStorage.removeItem(key); } catch { /* URL remains a recovery path. */ } };
const link = path => `/${path}${site ? `?site=${encodeURIComponent(site.id)}` : ''}${analysis ? `${site ? '&' : '?'}analysis=${encodeURIComponent(analysis.id)}` : ''}`;
const badge = text => `<span class="badge">${esc(text)}</span>`;
const warning = text => `<div class="notice"><span aria-hidden="true">ⓘ</span><span>${esc(text)}</span></div>`;
const heading = (eyebrow, title, text) => `<div class="page-heading"><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${text}</p></div>`;
const button = (text, path, secondary = false) => `<a class="button ${secondary ? 'secondary' : ''}" href="${link(path)}">${text} <span aria-hidden="true">↗</span></a>`;

function navigate(path) { history.pushState({}, '', link(path)); render(); }
document.addEventListener('click', e => {
  const a = e.target.closest('a');
  if (a && a.origin === location.origin && !a.hash && !a.pathname.startsWith('/api') && !a.hasAttribute('download') && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
    e.preventDefault(); history.pushState({}, '', a.href); render();
  }
});
window.addEventListener('popstate', render);

function shell(content) {
  root.innerHTML = `<header class="header"><a href="/" aria-label="SOLARYN Home">${SolarynLogo()}</a><nav aria-label="Main navigation"><a class="${!route() ? 'active' : ''}" href="/">Overview</a><a class="${route() ? 'active' : ''}" href="${link('site')}">Site analysis</a><a href="${link('evidence')}">Evidence</a></nav><span class="environment"><i></i> Local PoC <span>v0.1</span></span></header>
    ${route() ? `<div class="steps" role="navigation" aria-label="Analysis steps">${pages.map(([path, n, name]) => `<a href="${link(path)}" ${route() === path ? 'aria-current="step"' : ''}><span>${n}</span>${name}</a>`).join('')}</div>` : ''}
    <main id="main" tabindex="-1">${content}<div id="error" role="alert"></div></main>
    <footer><span>SOLARYN <span class="footer-sep">/</span> Climate-aware PV intelligence</span><span>Model transparency. Traceable evidence.</span></footer>`;
}
function error(message) { const el = document.querySelector('#error'); if (el) el.innerHTML = warning(message); }
async function action(fn) { try { await fn(); } catch (err) { error(err.message); } }

async function render() {
  const ticket = ++generation;
  if (map) { map.remove(); map = null; marker = null; }
  shell('<div class="loading" role="status">Loading workspace…</div>');
  try {
    const query = new URLSearchParams(location.search);
    const sid = query.get('site') || readKey('site');
    const aid = query.get('analysis') || readKey('analysis');
    const [loadedSite, loadedAnalysis] = await Promise.all([sid ? api.site(sid) : null, aid ? api.analysis(aid) : null]);
    if (ticket !== generation) return;
    site = loadedSite;
    analysis = loadedAnalysis && (!site || loadedAnalysis.site.id === site.id) ? loadedAnalysis : null;
    if (!site && analysis) site = analysis.site;
    switch (route()) {
      case '': {
        const recent = await api.sites(); if (ticket !== generation) return;
        shell(home(recent)); setupMap(false); break;
      }
      case 'site': shell(sitePage()); setupMap(true); bindSite(); break;
      case 'conditions':
        climate = site ? await api.climate(site.id) : null;
        if (ticket !== generation) return;
        shell(conditionsPage()); bindConditions();
        if (climate?.status === 'NOT_REQUESTED') retrieveConditions(false);
        break;
      case 'candidates': {
        [catalog, families] = await Promise.all([api.catalog(), api.families()]);
        if (ticket !== generation) return;
        if (!selected.size && analysis) selected = new Set(analysis.selected_modules.map(m => m.module_id));
        shell(candidatesPage()); bindCandidates(); break;
      }
      case 'processing': shell(processingPage()); bindRun(); break;
      case 'results':
        shell(resultsPage());
        if (analysis?.decision?.ranking?.length) {
          try { const visuals = await api.visuals(analysis.id); if (ticket === generation) document.querySelector('#decision-visuals').innerHTML = visuals.html; }
          catch (err) { if (ticket === generation) document.querySelector('#decision-visuals').innerHTML = warning(`Charts unavailable: ${err.message}. The saved results and downloads remain available.`); }
        }
        break;
      case 'evidence':
        climate = analysis ? analysis.climate_snapshot : site ? await api.climate(site.id) : null;
        if (ticket !== generation) return;
        shell(evidencePage()); break;
      default: shell(heading('404', 'Page not found', 'Return to the site analysis workspace.') + button('Open overview', ''));
    }
    document.title = `SOLARYN · ${pages.find(p => p[0] === route())?.[2] || 'Overview'}`;
    window.scrollTo({ top: 0, behavior: 'instant' });
    document.querySelector('#main')?.focus({ preventScroll: true });
  } catch (err) {
    if (ticket !== generation) return;
    shell(heading('WORKSPACE', 'Unable to load this view', 'Your saved records have not been changed.') + warning(err.message) + '<button class="button" id="retry">Retry</button> <button class="button secondary" id="reset">Start a new site</button>');
    document.querySelector('#retry').onclick = render;
    document.querySelector('#reset').onclick = () => { writeKey('site', null); writeKey('analysis', null); site = null; analysis = null; history.pushState({}, '', '/site'); render(); };
  }
}

function home(recent) {
  return `<section class="hero"><div class="hero-copy"><div class="eyebrow"><span class="yellow-line"></span> FROM SITE TO DECISION</div><h1>Choose the right<br>PV technology<br>for the <span>right site.</span></h1><p>From site conditions to technology performance<br class="desktop"> and lifetime value.</p>${button('Start Site Analysis', 'site')}<div class="hero-note">Physics-driven. Candidate-specific. Evidence-aware.</div></div><div class="hero-map"><div class="map-label">GLOBAL SITE EXPLORER <span>WGS84</span></div><div id="map" aria-label="World map preview"></div><div class="map-caption"><span class="crosshair">⊕</span><div><strong>Every decision starts somewhere.</strong><span>Select your project coordinate on the world map.</span></div></div></div></section>
    <section class="workflow"><div><span>01 / SITE</span><h3>Understand the environment</h3><p>Resource, operating temperature and site conditions.</p></div><div><span>02 / PERFORMANCE</span><h3>Compare actual candidates</h3><p>Module-specific parameters, common project assumptions.</p></div><div><span>03 / DECISION</span><h3>Make the evidence visible</h3><p>Modeled outcomes, lifetime value and clear limitations.</p></div></section>
    <section class="recent"><div class="section-title"><h2>Recent sites</h2><span>Saved locally on this computer</span></div>${recent.length ? `<div class="recent-grid">${recent.slice(0, 3).map(s => `<a class="recent-card" href="/conditions?site=${encodeURIComponent(s.id)}"><span class="eyebrow">SAVED SITE</span><strong>${coords(s)}</strong><span>${esc(s.created_at.slice(0, 10))} <b>↗</b></span></a>`).join('')}</div>` : '<div class="empty-inline">Your saved sites will appear here. Start with a coordinate.</div>'}</section>`;
}

function sitePage() {
  return heading('01 / SITE SELECTION', 'Where is your next project?', 'Click the map or enter coordinates. Your site is defined by its exact latitude and longitude.') +
    `<div class="site-layout"><section class="map-panel"><div class="map-label">WORLD MAP <span>Click to select · Drag to reposition</span></div><div id="map" aria-label="Interactive site selection map"></div><div id="tile-warning" role="status"></div><div class="map-bottom">WGS84 · Decimal degrees <span>No predefined locations</span></div></section><aside class="panel site-panel"><div class="eyebrow">PROJECT LOCATION</div><h2>Pin your site</h2><p>Use the map, or enter the coordinate directly.</p><form id="coordinate-form"><label for="latitude">Latitude <span>−90 to 90°</span></label><input id="latitude" name="latitude" type="number" step="any" min="-90" max="90" required placeholder="e.g. 12.3456" value="${site?.latitude ?? ''}"><label for="longitude">Longitude <span>−180 to 180°</span></label><input id="longitude" name="longitude" type="number" step="any" min="-180" max="180" required placeholder="e.g. 67.8901" value="${site?.longitude ?? ''}"><button class="button secondary full" type="submit">Update map <span>⊕</span></button></form><div class="selected-site"><span class="eyebrow">SELECTED COORDINATE</span><strong id="selected-coordinate" aria-live="polite">${coords(site)}</strong></div><button id="continue" class="button full" ${site ? '' : 'disabled'}>Continue to site conditions <span>→</span></button><p class="small">Provider coverage is checked during resource retrieval. Coordinates are never substituted.</p></aside></div>`;
}

function setupMap(editable) {
  if (!window.L) { error('Map library unavailable. You can still enter coordinates manually.'); return; }
  map = L.map('map', { zoomControl: editable, scrollWheelZoom: editable, worldCopyJump: true, minZoom: 1, maxZoom: 18 }).setView(site ? [site.latitude, site.longitude] : [18, 0], site && editable ? 6 : 2);
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors', maxZoom: 19 }).addTo(map);
  tiles.on('tileerror', () => { const el = document.querySelector('#tile-warning'); if (el) el.textContent = 'Map tiles unavailable. Enter coordinates manually to continue.'; });
  if (editable) {
    map.on('click', event => setCoordinate(event.latlng.lat, event.latlng.wrap().lng));
    if (site) setCoordinate(site.latitude, site.longitude);
  }
}
let draft = null;
function setCoordinate(latitude, longitude) {
  draft = { latitude, longitude };
  document.querySelector('#latitude').value = latitude;
  document.querySelector('#longitude').value = longitude;
  document.querySelector('#selected-coordinate').textContent = coords(draft);
  document.querySelector('#continue').disabled = false;
  if (!map) return;
  if (marker) marker.setLatLng([latitude, longitude]);
  else {
    marker = L.marker([latitude, longitude], { draggable: true, title: 'Selected site — drag to reposition', icon: L.divIcon({ className: 'site-marker', html: '<span></span>', iconSize: [26, 26], iconAnchor: [13, 13] }) }).addTo(map);
    marker.on('dragend', () => { const p = marker.getLatLng().wrap(); setCoordinate(Math.max(-90, Math.min(90, p.lat)), p.lng); });
  }
}
function bindSite() {
  draft = site ? { latitude: site.latitude, longitude: site.longitude } : null;
  const form = document.querySelector('#coordinate-form');
  const readForm = () => {
    if (!form.reportValidity()) return null;
    return { latitude: Number(form.elements.latitude.value), longitude: Number(form.elements.longitude.value) };
  };
  form.oninput = () => { document.querySelector('#continue').disabled = !form.checkValidity(); };
  form.onsubmit = event => { event.preventDefault(); const p = readForm(); if (p) { setCoordinate(p.latitude, p.longitude); map?.panTo([p.latitude, p.longitude]); } };
  document.querySelector('#continue').onclick = () => action(async () => {
    const p = readForm(); if (!p) return;
    const btn = document.querySelector('#continue'); btn.disabled = true; btn.textContent = 'Saving site…';
    try {
      site = await api.saveSite(p); analysis = null; climate = null;
      writeKey('site', site.id); writeKey('analysis', null); navigate('conditions');
    } finally { btn.disabled = false; btn.textContent = 'Continue to site conditions →'; }
  });
}

function conditionsPage() {
  if (!site) return noSite();
  const labels = { annual_ghi: 'Annual solar resource · GHI', irradiance: 'Mean hourly GHI', air_temperature: 'Mean air temperature · 2 m', wind_speed: 'Mean wind speed · 10 m', relative_humidity: 'Mean relative humidity · 2 m' };
  return heading('02 / SITE CONDITIONS', 'The environment behind the decision.', `Selected site · ${coords(site)}`) +
    `<form id="climate-form" class="climate-toolbar"><label for="climate-year">Reference year</label><input id="climate-year" type="number" min="2005" max="${new Date().getFullYear() - 1}" value="${climate.year}" required><button class="button" id="climate-load" type="submit">Load PVGIS + NASA POWER</button><button class="button secondary" id="climate-refresh" type="button">Refresh sources</button><span id="climate-progress" role="status" aria-live="polite">${climate.id ? 'Saved snapshot' : 'Ready to retrieve hourly data'}</span></form>` +
    climate.warnings.map(warning).join('') +
    `<div class="metric-grid">${Object.keys(labels).map(k => `<article class="panel metric"><span>${labels[k]}</span><strong>${fmt(climate.metrics[k])}</strong><small>${esc(climate.units[k])}</small><small class="metric-source">${esc(climate.metric_sources[k] || 'Unavailable')} · ${climate.period || 'No data'}</small></article>`).join('')}</div>
    <div class="conditions-grid"><section class="panel"><div class="section-title"><h2>Monthly solar resource</h2><span>Horizontal GHI · kWh/m²</span></div>${monthlyChart(climate)}<p class="small">Yellow: PVGIS · Navy: NASA POWER. Missing months stay blank.</p></section><section class="panel"><h2>Resource cross-check</h2><dl><dt>PVGIS annual GHI</dt><dd>${fmt(climate.crosscheck.pvgis_annual_ghi_kwh_m2)} kWh/m²</dd><dt>NASA annual GHI</dt><dd>${fmt(climate.crosscheck.nasa_annual_ghi_kwh_m2)} kWh/m²</dd><dt>NASA relative to PVGIS</dt><dd>${fmt(climate.crosscheck.difference_pct)} %</dd><dt>Comparison</dt><dd>${badge(climate.crosscheck.status)}</dd><dt>Reference year</dt><dd>${climate.period || 'Not retrieved'}</dd><dt>Geometry</dt><dd>Horizontal · horizon shading off</dd><dt>Displayed main source</dt><dd>${esc(climate.provider || 'Unavailable')}</dd></dl><p class="small">${esc(climate.crosscheck.definition || 'Both providers must return a complete solar year for comparison.')}</p></section></div>
    <section class="provider-grid">${climate.providers.map(providerPanel).join('')}</section><div class="actions">${button('Edit site', 'site', true)}${button('Explore module candidates', 'candidates')}</div>`;
}

function monthlyChart(snapshot) {
  const series = snapshot.providers.filter(p => p.monthly.length);
  if (!series.length) return '<div class="chart-empty"><strong>Waiting for hourly source data</strong><p>Both providers are retrieved for the selected coordinate.</p></div>';
  // Chart scaling only. All monthly energy values are calculated by the backend.
  const maximum = Math.max(1, ...series.flatMap(p => p.monthly.map(m => m.ghi_kwh_m2 ?? 0)));
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `<div class="resource-chart" role="img" aria-label="Monthly GHI comparison. Exact values are available in the table below.">${months.map((name,i) => `<div class="month-group"><div class="month-bars">${['PVGIS','NASA_POWER'].map(provider => { const entry = snapshot.providers.find(p => p.provider === provider)?.monthly.find(m => m.month === i+1); const n = entry?.ghi_kwh_m2; return `<div class="resource-bar ${provider === 'PVGIS' ? 'pvgis' : 'nasa'}" style="height:${n == null ? 0 : 100*n/maximum}%" title="${name} ${provider}: ${fmt(n)} kWh/m²"></div>`; }).join('')}</div><span>${name}</span></div>`).join('')}</div><details class="monthly-details"><summary>View monthly values</summary><table><thead><tr><th>Month</th><th>PVGIS · kWh/m²</th><th>NASA · kWh/m²</th></tr></thead><tbody>${months.map((name,i) => `<tr><td>${name}</td>${['PVGIS','NASA_POWER'].map(p => `<td>${fmt(snapshot.providers.find(s => s.provider === p)?.monthly.find(m => m.month === i+1)?.ghi_kwh_m2)}</td>`).join('')}</tr>`).join('')}</tbody></table></details>`;
}

function providerPanel(p) {
  return `<article class="panel provider-panel"><div class="section-title"><h2>${esc(p.provider)}</h2>${badge(p.status)}</div>${p.error ? warning(p.error) : `<dl><dt>Annual GHI</dt><dd>${fmt(p.metrics.annual_ghi)} kWh/m²</dd><dt>Solar coverage</dt><dd>${p.coverage?.valid_hours.ghi_w_m2} / ${p.coverage?.expected_hours} hours</dd><dt>Retrieved</dt><dd>${esc(p.retrieved_at)}</dd><dt>Data access</dt><dd>${p.cache_hit ? 'Saved source reused' : 'Retrieved from provider'}</dd></dl>`}<details><summary>Provenance & quality</summary>${p.warnings.map(warning).join('')}<pre>${esc(JSON.stringify({source_id:p.source_id, normalizer:p.normalizer_version, sha256:p.raw_sha256, coverage:p.coverage, provenance:p.provenance},null,2))}</pre></details>${p.source_id ? `<div class="source-downloads"><a href="/api/v1/climate-sources/${encodeURIComponent(p.source_id)}/export" download>Hourly snapshot JSON ↓</a><a href="/api/v1/climate-sources/${encodeURIComponent(p.source_id)}/export?raw=true" download>Original response ↓</a></div>` : ''}</article>`;
}

function bindConditions() {
  if (!site) return;
  document.querySelector('#climate-form').onsubmit = e => { e.preventDefault(); retrieveConditions(false); };
  document.querySelector('#climate-refresh').onclick = () => retrieveConditions(true);
}

async function retrieveConditions(refresh) {
  if (!site || !document.querySelector('#climate-form')?.reportValidity()) return;
  const siteId = site.id, ticket = generation;
  const year = Number(document.querySelector('#climate-year').value);
  const key = `${siteId}:${year}`;
  const controls = ['#climate-load','#climate-refresh','#climate-year'];
  controls.forEach(selector => { document.querySelector(selector).disabled = true; });
  document.querySelector('#climate-progress').textContent = 'Retrieving a full year from PVGIS and NASA POWER… This can take up to 90 seconds.';
  try {
    if (!climateRequests.has(key)) climateRequests.set(key, api.retrieveClimate(siteId, year, refresh));
    const result = await climateRequests.get(key);
    if (ticket !== generation || route() !== 'conditions' || site?.id !== siteId) return;
    climate = result; shell(conditionsPage()); bindConditions();
  } catch (err) {
    if (ticket === generation) { error(err.message); document.querySelector('#climate-progress').textContent = 'Retrieval failed. You can retry.'; }
  } finally {
    climateRequests.delete(key);
    if (ticket === generation) controls.forEach(selector => { const el = document.querySelector(selector); if (el) el.disabled = false; });
  }
}
function noSite() { return heading('SITE REQUIRED', 'Start with your project location.', 'Select a coordinate before continuing through the analysis.') + button('Select a site', 'site'); }
const filterFields = [['technology_family','Technology family'],['technology_subtype','Technology subtype'],['manufacturer','Manufacturer'],['monofacial_or_bifacial','Module face'],['application','Application'],['commercial_status','Commercial status'],['evidence_level','Evidence level']];
function familyMatch(m) {
  return filterFields.every(([key]) => !filters[key] || (m[key] || '').split('|').includes(filters[key]));
}
function candidatesPage() {
  const toolbar = filterFields.map(([key,label]) => {
    const options = key === 'technology_family' ? families : [...new Set(catalog.modules.flatMap(m => (m[key] || '').split('|')).filter(Boolean))].sort();
    return `<label>${label}<select data-filter="${key}"><option value="">All</option>${options.map(v=>`<option value="${esc(v)}" ${filters[key]===v?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
  }).join('');
  return heading('03 / CANDIDATE SELECTION', 'Compare modules. Follow the evidence.', 'Select 3–10 exact SKUs. Families and architecture describe the catalog; candidate evidence determines the model.') + warning(catalog.warning) +
    `<div class="catalog-filters">${toolbar}</div><p id="selection-count">${selected.size} selected</p><div class="module-grid">${catalog.modules.filter(familyMatch).map(m=>`<article class="panel module-card"><label class="module-select"><input type="checkbox" data-module="${esc(m.module_id)}" aria-label="Select ${esc(m.manufacturer)} ${esc(m.model)}" ${selected.has(m.module_id)?'checked':''}><span><strong>${esc(m.manufacturer)}</strong><span class="model">${esc(m.model)}</span></span></label><p>${badge(m.commercial_status)} ${badge('SCREENING ONLY')}</p><p>${esc(m.technology_family)} · ${esc(m.technology_subtype)}</p><p class="small">${esc(m.cell_architecture)} · ${esc(m.module_architecture)}</p><dl><dt>Power</dt><dd>${value(m.rated_power_w)} W</dd><dt>Efficiency</dt><dd>${value(m.efficiency_pct)} %</dd><dt>Temperature coefficient</dt><dd>${value(m.temperature_coefficient_pct_per_c)} %/°C</dd><dt>Module face / bifaciality</dt><dd>${esc(m.monofacial_or_bifacial)} / ${value(m.bifaciality_pct)} %</dd><dt>Application</dt><dd>${esc(m.application?.replaceAll('|',' / ') || 'Unknown')}</dd><dt>Datasheet regions</dt><dd>${esc(m.market_regions?.replaceAll('|',' / ') || 'Not established')}</dd><dt>Electrical model</dt><dd>Path C · evidence limited</dd></dl><details><summary>Official source &amp; evidence</summary><p>${esc(m.source_note)}</p><p>Checked ${esc(m.source_checked_at)} · Revision ${esc(m.datasheet_revision || 'Not established')}</p><p class="small">IEC matrix, IAM, spectral and independent field evidence: not supplied for this release. Warranty terms do not set modeled degradation.</p><a href="${esc(m.source_url)}" target="_blank" rel="noopener noreferrer">Manufacturer datasheet ↗</a></details></article>`).join('') || '<div class="panel"><h2>No eligible catalog records in this filter</h2><p>Tandem remains evidence gated: no verified exact procurable SKU and model inputs are seeded. No placeholder can be selected.</p></div>'}</div><div class="actions"><p class="small">Hidden selections remain selected when you change filters.</p><button class="button" id="clear-selection">Clear selection</button><button class="button" id="prepare" ${selected.size < 3 || !site ? 'disabled' : ''}>Prepare analysis →</button></div>${!site ? button('Select a site to continue','site',true):''}`;
}
function bindCandidates() {
  document.querySelectorAll('[data-filter]').forEach(input => input.onchange = () => { filters[input.dataset.filter] = input.value; shell(candidatesPage()); bindCandidates(); });
  document.querySelector('#clear-selection').onclick = () => { selected.clear(); shell(candidatesPage()); bindCandidates(); };
  document.querySelectorAll('[data-module]').forEach(input => input.onchange = () => {
    input.checked ? selected.add(input.dataset.module) : selected.delete(input.dataset.module);
    if (selected.size > 10) { selected.delete(input.dataset.module); input.checked = false; error('Select up to ten candidates.'); }
    document.querySelector('#selection-count').textContent = `${selected.size} selected`;
    document.querySelector('#prepare').disabled = selected.size < 3 || !site;
  });
  document.querySelector('#prepare').onclick = () => action(async () => {
    const btn = document.querySelector('#prepare'); btn.disabled = true; btn.textContent = 'Saving request…';
    try { analysis = await api.analyse(site.id, [...selected]); writeKey('analysis', analysis.id); navigate('processing'); }
    finally { btn.disabled = false; btn.textContent = 'Prepare analysis →'; }
  });
}
function processingPage() {
  return heading('04 / ANALYSIS', 'A transparent path to your result.', 'Each stage reports its actual backend state.') +
    (analysis ? warning(analysis.manifest ? analysis.warnings[0] : 'This request is saved. Review the project assumptions and run the provisional comparison.') : warning('No analysis request has been saved. Select at least three modules to prepare a request.')) +
    `${analysis ? configurationForm() : ''}<section class="panel pipeline">${(analysis?.stages || ['SITE', 'CLIMATE', 'TECHNOLOGIES', 'PHYSICS', 'LIFETIME', 'ECONOMICS', 'RECOMMENDATION'].map(name => ({ name, status: 'NOT_STARTED' }))).map((s, i) => `<div><span class="stage-number">${String(i + 1).padStart(2, '0')}</span><strong>${s.name}</strong>${badge(s.status)}</div>`).join('')}</section><div class="actions">${button('Review candidates', 'candidates', true)}${button('View result workspace', 'results')}</div>`;
}
function resultsPage() {
  if (analysis?.decision?.ranking?.length) return calculatedResults();
  if (analysis?.status === 'CANNOT_RECOMMEND') return heading('05 / RESULTS','A fair comparison could not be calculated.',analysis.explanation) + analysis.candidate_failures.map(f=>warning(`${f.module_id}: ${f.reason}`)).join('') + button('Review candidate inputs','candidates');
  return `<div class="report-brand">${SolarynLogo('report')}</div>` + heading('05 / RESULTS', 'The recommendation, with its reasoning.', site ? `Selected site · ${coords(site)}` : 'Your comparison workspace') +
    warning(analysis ? analysis.warnings[0] : 'No calculation is available. Prepare an analysis from the candidate catalog.') +
    `<section class="recommendation panel"><div><div class="eyebrow">RECOMMENDED CANDIDATE</div><h2>Awaiting calculation</h2><p>Recommendation strength: Not evaluated</p></div>${badge('AWAITING CALCULATION')}</section><div class="ranking-grid">${[1, 2, 3].map(n => `<article class="panel rank-card"><span class="rank">#${n}</span><h3>Awaiting ranked candidate</h3><p>Rank is assigned by the backend.</p><dl><dt>Annual specific energy</dt><dd>— kWh/kWp</dd><dt>Lifetime energy</dt><dd>— kWh/kWp</dd><dt>Relative difference</dt><dd>— %</dd><dt>Module price</dt><dd>— €/W</dd><dt>Δ€/W</dt><dd>—</dd><dt>Evidence quality</dt><dd>Not evaluated</dd></dl></article>`).join('')}</div><section class="panel why"><h2>Why this recommendation?</h2><p>No physical or economic contributions have been calculated.</p><p class="small">Calculated effects will appear here with their stored values and evidence.</p></section><div class="actions">${button('Review candidates', 'candidates', true)}${button('Inspect evidence', 'evidence')}</div>`;
}

function configurationForm() {
  const c = analysis.configuration || {objective:'annual_dc',tilt_deg:0,azimuth_deg:180,albedo:0.2,soiling_pct:0,u0:25,u1:6.84,wind_factor:1};
  const field = (name, label, val, min, max, step = 'any') => `<label>${label}<input type="number" name="${name}" value="${val ?? ''}" min="${min}" max="${max}" step="${step}" required></label>`;
  return `<form id="run-form" class="panel configuration"><div class="eyebrow">PROJECT ASSUMPTIONS</div><h2>Define the comparison</h2><p class="small">Starting scenario: horizontal, front-side DC screening. Edit these shared assumptions for your project. Each run saves a new immutable result.</p><div class="input-grid"><label>Project application<select name="application">${['GENERAL_SCREENING','ROOFTOP','UTILITY','BIPV_FACADE'].map(v=>`<option value="${v}" ${(c.application || 'GENERAL_SCREENING')===v?'selected':''}>${v.replaceAll('_',' ')}</option>`).join('')}</select></label><label>Project market · two-letter country code<input name="market_region" value="${esc(c.market_region || '')}" pattern="[A-Z]{2}" maxlength="2" placeholder="US, AU, NZ…"></label></div><p class="small">Declared application and market exclude incompatible datasheet variants. An undeclared market supports screening only, with procurement verification still required.</p><label>Ranking objective<select name="objective">${[['annual_dc','Annual DC specific energy'],['annual_ac','Annual AC specific energy'],['lifetime_dc','Lifetime DC specific energy'],['procurement_headroom','Procurement headroom · €/W']].map(([v,t])=>`<option value="${v}" ${c.objective===v?'selected':''}>${t}</option>`).join('')}</select></label><div class="input-grid">${field('tilt_deg','Tilt · degrees',c.tilt_deg,0,90)}${field('azimuth_deg','Azimuth · north 0°, east 90°',c.azimuth_deg,0,359.99)}${field('albedo','Ground albedo · fraction',c.albedo,0,1)}${field('soiling_pct','Common soiling · %',c.soiling_pct,0,50)}</div><details><summary>Shared temperature assumptions</summary><p class="small">Faiman defaults are a screening assumption, not measurements of these products. Source wind is at 10 m. A factor of 1 uses it without a height correction. No technology-specific cooling bonus is applied.</p><div class="input-grid">${field('u0','U0 · W/m²/K',c.u0,.01,100)}${field('u1','U1 · W/m²/K per m/s',c.u1,0,30)}${field('wind_factor','Source wind multiplier',c.wind_factor,.01,2)}</div></details>
    <label class="toggle"><input type="checkbox" id="enable-life" ${c.lifetime?'checked':''}> Add a common lifetime scenario</label><fieldset id="life-fields" ${c.lifetime?'':'disabled'}><div class="input-grid">${field('years','Project life · years',c.lifetime?.years,1,50,1)}${field('degradation_pct','Common annual degradation · %',c.lifetime?.degradation_pct,0,10)}</div><p class="small">Supply a scenario; warranty figures are not used as measured degradation.</p></fieldset>
    <label class="toggle"><input type="checkbox" id="enable-ac" ${c.ac?'checked':''}> Add an AC conversion scenario</label><fieldset id="ac-fields" ${c.ac?'':'disabled'}><div class="input-grid">${field('dc_ac_ratio','DC / AC ratio',c.ac?.dc_ac_ratio,.5,3)}${field('efficiency','Inverter efficiency · fraction',c.ac?.efficiency,.5,1)}${field('availability','Availability · fraction',c.ac?.availability,.01,1)}${field('curtailment','Curtailment · fraction',c.ac?.curtailment,0,.99)}</div></fieldset>
    <label class="toggle"><input type="checkbox" id="enable-econ" ${c.economics?'checked':''}> Add supplied commercial inputs</label><fieldset id="econ-fields" ${c.economics?'':'disabled'}><p class="small">Requires lifetime and AC inputs. EUR switching threshold; end-of-year discounting. Enter the present value of candidate-specific non-module costs per installed DC watt, including explicit zero where excluded. This is not full LCOE.</p><label>Economic reference<select name="reference_id"><option value="">Choose a selected candidate</option>${analysis.selected_modules.map(m=>`<option value="${esc(m.module_id)}" ${c.economics?.reference_id===m.module_id?'selected':''}>${esc(m.manufacturer)} ${esc(m.model)}</option>`).join('')}</select></label><div class="input-grid">${field('energy_value_eur_kwh','Net AC energy value · €/kWh',c.economics?.energy_value_eur_kwh,0,10)}${field('discount_rate_pct','Annual discount rate · %',c.economics?.discount_rate_pct,0,30)}</div>${analysis.selected_modules.map((m,i)=>`<h3>${esc(m.manufacturer)} ${esc(m.model)}</h3><div class="input-grid">${field(`quote_${i}`,'Module quote · €/W',c.economics?.quotes_eur_w[m.module_id],0,100)}${field(`cost_${i}`,'PV non-module costs · €/W',c.economics?.incremental_cost_pv_eur_w[m.module_id],0,100)}</div>`).join('')}</fieldset><div class="actions"><p class="small">Provisional datasheet path · same resource for every candidate</p><button class="button" id="run-analysis">Run comparison →</button></div><p id="run-progress" role="status" aria-live="polite"></p></form>`;
}

function bindRun() {
  const form = document.querySelector('#run-form');
  if (!form) return;
  for (const name of ['life','ac','econ']) document.querySelector(`#enable-${name}`).onchange = event => { document.querySelector(`#${name}-fields`).disabled = !event.target.checked; };
  form.onsubmit = event => { event.preventDefault(); action(async () => {
    const get = name => Number(form.elements[name].value);
    const config = Object.fromEntries(['tilt_deg','azimuth_deg','albedo','soiling_pct','u0','u1','wind_factor'].map(k=>[k,get(k)]));
    config.objective = form.elements.objective.value;
    config.application = form.elements.application.value;
    config.market_region = form.elements.market_region.value || null;
    if (document.querySelector('#enable-life').checked) config.lifetime = {years:get('years'),degradation_pct:get('degradation_pct')};
    if (document.querySelector('#enable-ac').checked) config.ac = Object.fromEntries(['dc_ac_ratio','efficiency','availability','curtailment'].map(k=>[k,get(k)]));
    if (document.querySelector('#enable-econ').checked) config.economics = {reference_id:form.elements.reference_id.value,energy_value_eur_kwh:get('energy_value_eur_kwh'),discount_rate_pct:get('discount_rate_pct'),quotes_eur_w:Object.fromEntries(analysis.selected_modules.map((m,i)=>[m.module_id,get(`quote_${i}`)])),incremental_cost_pv_eur_w:Object.fromEntries(analysis.selected_modules.map((m,i)=>[m.module_id,get(`cost_${i}`)]))};
    const btn = document.querySelector('#run-analysis'), ticket = generation, requestId = analysis.id;
    btn.disabled = true; document.querySelector('#run-progress').textContent = 'Calculating the frozen hourly year for each selected candidate…';
    try { const result = await api.run(requestId, config); if (ticket !== generation) return; analysis = result; writeKey('analysis', analysis.id); navigate('results'); }
    finally { btn.disabled = false; const progress = document.querySelector('#run-progress'); if (progress) progress.textContent = ''; }
  }); };
}

function optionalScenarioSummary() {
  const c = analysis.configuration;
  const e = c.economics;
  const ref = e ? analysis.selected_modules.find(m=>m.module_id===e.reference_id) : null;
  return `<dl>${c.lifetime ? `<dt>Project life</dt><dd>${c.lifetime.years} years</dd><dt>Common degradation</dt><dd>${c.lifetime.degradation_pct} %/year</dd>` : ''}${c.ac ? `<dt>DC / AC ratio</dt><dd>${c.ac.dc_ac_ratio}</dd><dt>Inverter efficiency</dt><dd>${c.ac.efficiency} fraction</dd><dt>Availability</dt><dd>${c.ac.availability} fraction</dd><dt>Curtailment</dt><dd>${c.ac.curtailment} fraction</dd>` : ''}${e ? `<dt>Economic reference</dt><dd>${esc(ref?.manufacturer)} ${esc(ref?.model)}</dd><dt>Energy value</dt><dd>${e.energy_value_eur_kwh} €/kWh net AC</dd><dt>Discount rate</dt><dd>${e.discount_rate_pct} %/year</dd>` : ''}</dl>`;
}

function calculatedResults() {
  const d = analysis.decision, leader = d.ranking[0];
  const objective = {annual_dc:'Annual DC specific energy',annual_ac:'Annual AC specific energy',lifetime_dc:'Lifetime DC specific energy',procurement_headroom:'Procurement headroom'}[d.objective];
  const money = n => n == null ? 'Not supplied' : Number(n).toFixed(4);
  return heading('05 / RESULTS','Your recommendation, with its limits.',`${coords(analysis.site)} · ${esc(analysis.climate_snapshot.provider)} · ${analysis.climate_snapshot.year}`) +
    `<section class="recommendation panel"><div><div class="eyebrow">RECOMMENDED · PROVISIONAL SCREENING</div><h2>${esc(leader.manufacturer)} ${esc(leader.model)}</h2><p>Recommendation strength: <strong>${esc(d.strength)}</strong><br>Scientific status: Model-based / provisional</p><p>${esc(objective)} · ${d.objective_unit === "EUR/W" ? money(leader.objective_value) : fmt(leader.objective_value)} ${esc(d.objective_unit)}</p></div>${badge('External validation pending')}</section>` +
    downloadButtons() + warning(d.strength_reason) + (d.co_leaders.length>1 ? warning('Numerical co-leaders: no established physical preference. Stable module IDs determine display order.') : '') +
    `<div class="ranking-grid">${d.top_three.map(r=>`<article class="panel rank-card"><span class="rank">#${r.rank}</span><h3>${esc(r.manufacturer)}<br>${esc(r.model)}</h3><p>${esc(r.model_path)} · ${esc(r.evidence)}</p><dl><dt>Annual DC energy</dt><dd>${fmt(r.annual_dc_kwh_kwp)} kWh/kWp</dd><dt>Annual AC energy</dt><dd>${fmt(r.annual_ac_kwh_kwp)} kWh/kWp</dd><dt>Lifetime DC energy</dt><dd>${fmt(r.lifetime_dc_kwh_kwp)} kWh/kWp</dd><dt>DC difference from leader</dt><dd>${fmt(r.dc_difference_from_leader_pct)} %</dd><dt>Module quote</dt><dd>${money(r.quote_eur_w)} ${r.quote_eur_w==null?'':'€/W'}</dd><dt>Maximum justified premium</dt><dd>${money(r.max_premium_eur_w)} ${r.max_premium_eur_w==null?'':'€/W'}</dd><dt>Procurement headroom</dt><dd>${money(r.headroom_eur_w)} ${r.headroom_eur_w==null?'':'€/W'}</dd></dl></article>`).join('')}</div><section class="panel why"><h2>Why this recommendation?</h2><p>${esc(analysis.explanation)}</p><p class="small">Objective: ${esc(objective)}. Equal installed DC capacity; prices and degradation never come from technology labels.</p></section>
    <section id="decision-visuals" aria-label="Decision dashboard"><p role="status">Loading saved analysis charts…</p></section><section class="panel sources"><h2>Every calculated candidate</h2>${d.ranking.map(r=>`<details><summary>#${r.rank} · ${esc(r.manufacturer)} ${esc(r.model)} · ${fmt(r.annual_dc_kwh_kwp)} kWh/kWp DC</summary><p class="small">${esc(r.extrapolation_status)}</p><dl>${Object.entries(r.contributions).map(([k,v])=>`<dt>${esc(k.replaceAll('_',' '))}</dt><dd>${fmt(v)}</dd>`).join('')}</dl><div class="table-wrap"><table><thead><tr><th>Month</th><th>DC · kWh/kWp</th><th>AC · kWh/kWp</th></tr></thead><tbody>${r.monthly.map(m=>`<tr><td>${m.month}</td><td>${fmt(m.dc_kwh_kwp)}</td><td>${fmt(m.ac_kwh_kwp)}</td></tr>`).join('')}</tbody></table></div></details>`).join('')}${analysis.candidate_failures.map(f=>warning(`${f.module_id}: ${f.reason}`)).join('')}</section>
    <section class="panel sources"><h2>Frozen project assumptions</h2>${optionalScenarioSummary()}${analysis.assumptions.map(a=>`<p>${esc(a)}</p>`).join('')}<p>Tilt ${analysis.configuration.tilt_deg}° · Azimuth ${analysis.configuration.azimuth_deg}° · Albedo ${analysis.configuration.albedo}</p></section><div class="actions">${button('Change assumptions / new run','processing',true)}${button('Inspect evidence','evidence')}</div>`;
}
function downloadButtons() {
  return `<div class="download-actions"><a class="button" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/report" download>Download EPC Report ↓</a><a class="button secondary" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/package" download>Download Evidence Package ↓</a><a href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/report?inline=true" target="_blank" rel="noopener">Preview report ↗</a></div>`;
}
function evidencePage() {
  const rows = analysis?.selected_modules || [];
  return heading('06 / EVIDENCE', 'An inspectable chain of evidence.', 'Sources, assumptions and model scope belong alongside every decision.') + (analysis?.decision?.ranking?.length ? downloadButtons() : '') +
    `<div class="conditions-grid"><section class="panel"><h2>Analysis provenance</h2><dl><dt>Climate source</dt><dd>${esc(climate?.provider || "Not retrieved")} ${esc(climate?.period || "")}</dd><dt>Module source</dt><dd>${esc(analysis?.catalog_source || 'Existing repository catalog')}</dd><dt>Model path</dt><dd>${esc(analysis?.model_path || "Not run")}</dd><dt>Model version</dt><dd>${esc(analysis?.model_version || "Not assigned")}</dd><dt>Evidence level</dt><dd>${analysis?.manifest ? "Provisional datasheet screening" : "Pending review"}</dd><dt>Extrapolation</dt><dd>${esc(analysis?.extrapolation || "Not calculated")}</dd><dt>Validation status</dt><dd>${esc(analysis?.validation_status || 'NOT_RUN')}</dd><dt>Assumptions</dt><dd>${analysis?.assumptions.length ? analysis.assumptions.map(esc).join("<br><br>") : "None applied; calculation has not run"}</dd></dl></section><section class="panel"><h2>Warnings & limitations</h2>${(analysis?.warnings || ['PV performance and recommendation services are not connected to this flow.', 'Current commercial availability requires source verification.']).map(warning).join('')}<p class="small">Software checks do not establish scientific validation.</p>${analysis ? `<a class="button secondary" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/export" download>Export frozen analysis JSON ↓</a>` : ''}</section></div>${climate?.providers?.length ? `<section class="provider-grid">${climate.providers.map(providerPanel).join("")}</section>` : ""}${analysis?.manifest ? `<section class="panel sources"><h2>Reproducibility manifest</h2><pre class="manifest">${esc(JSON.stringify(analysis.manifest,null,2))}</pre><p class="small">The export includes the normalized hourly source, exact module inputs, configuration, code hashes and runtime versions. Source response downloads preserve the original bytes.</p></section>` : ""}<section class="panel sources"><h2>Selected module sources</h2>${rows.length ? rows.map(m => `<div><strong>${esc(m.manufacturer)} · ${esc(m.model)}</strong><p>${esc(m.source_note || 'No source note')}</p>${m.source_url && /^https:\/\//.test(m.source_url) ? `<a href="${esc(m.source_url)}" target="_blank" rel="noopener noreferrer">Open recorded manufacturer source ↗</a>` : '<span>Source unavailable</span>'}</div>`).join('') : '<p>Select modules to inspect their source records.</p>'}</section>`;
}
render();
