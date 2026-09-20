import { api, request } from './api.js?v=admin1';
import { SolarynLogo } from './logo.js';

const root = document.querySelector('#app');

const stageDefs = [
  { n: '01', name: 'Site & Project', path: 'site' },
  { n: '02', name: 'Climate Fingerprint', path: 'conditions' },
  { n: '03', name: 'Technology Behaviour', path: 'candidates' },
  { n: '04', name: 'Lifetime Performance', path: 'processing' },
  { n: '05', name: 'Lifetime Economics', path: 'economics' },
  { n: '06', name: 'Decision', path: 'results' },
];

const routeTitles = {
  '': 'Overview', site: 'Site & Project', conditions: 'Climate Fingerprint',
  candidates: 'Technology Behaviour', processing: 'Lifetime Performance',
  economics: 'Lifetime Economics', results: 'Decision', evidence: 'Evidence',
};

let site = null;
let adminProfile = null;
let climate = null;
let catalog = null;
let families = [];
let analysis = null;
let map = null;
let marker = null;
let draft = null;
let selected = new Set();
let filters = {};
let generation = 0;
let placeName = null;
let draftPlaceName = null;
let geocodeTimer = null;
let geocodeController = null;

const climateRequests = new Map();
const fmt = n => n == null || Number.isNaN(Number(n)) ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 1 });
const fmt2 = n => n == null || Number.isNaN(Number(n)) ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 });
const money = n => n == null || Number.isNaN(Number(n)) ? 'Not available' : `€${Number(n).toFixed(4)}/W`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const value = v => v == null ? '—' : esc(v);
const coords = s => s ? `${Number(s.latitude).toFixed(4)}°, ${Number(s.longitude).toFixed(4)}°` : 'No site selected';
const route = () => location.pathname.slice(1);
const readKey = key => { try { return sessionStorage.getItem(key); } catch { return null; } };
const writeKey = (key, val) => { try { val ? sessionStorage.setItem(key, val) : sessionStorage.removeItem(key); } catch { /* URL remains recovery path. */ } };
const link = path => `/${path}${site ? `?site=${encodeURIComponent(site.id)}` : ''}${analysis ? `${site ? '&' : '?'}analysis=${encodeURIComponent(analysis.id)}` : ''}`;
const badge = (text, tone = '') => `<span class="badge ${tone ? `badge-${tone}` : ''}">${esc(text)}</span>`;
const warning = text => `<div class="notice"><span class="notice-icon" aria-hidden="true">i</span><span>${esc(text)}</span></div>`;
const heading = (eyebrow, title, text) => `<div class="page-heading"><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p>${esc(text)}</p></div>`;
const button = (text, path, secondary = false) => `<a class="button ${secondary ? 'secondary' : ''}" href="${link(path)}">${esc(text)} <span aria-hidden="true">→</span></a>`;
const unavailable = text => `<span class="unavailable">${esc(text || 'Not available in this analysis')}</span>`;

function navigate(path) {
  history.pushState({}, '', link(path));
  render();
}

document.addEventListener('click', e => {
  const a = e.target.closest('a');
  if (a && a.origin === location.origin && !a.hash && !a.pathname.startsWith('/api') && !a.hasAttribute('download') && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
    e.preventDefault();
    history.pushState({}, '', a.href);
    render();
  }
});
window.addEventListener('popstate', render);

function currentClimate() {
  return analysis?.climate_snapshot || climate || null;
}

function moduleFor(moduleId) {
  return analysis?.selected_modules?.find(m => m.module_id === moduleId) || catalog?.modules?.find(m => m.module_id === moduleId) || null;
}

function stageStatus(index) {
  const snapshot = currentClimate();
  const ranking = analysis?.decision?.ranking || [];
  const d = analysis?.decision || {};
  const c = analysis?.configuration || null;
  if (index === 0) return site ? 'Selected' : 'Ready';
  if (index === 1) {
    if (!snapshot || snapshot.status === 'NOT_REQUESTED') return 'Not retrieved';
    if (snapshot.status === 'AVAILABLE') return 'Retrieved';
    if (snapshot.status === 'PARTIAL') return 'Partial';
    return 'Unavailable';
  }
  if (index === 2) {
    if (ranking.length) return 'Compared';
    if (analysis?.selected_modules?.length || selected.size) return 'Selected';
    return 'Not selected';
  }
  if (index === 3) {
    if (!analysis) return 'Not available';
    if (!ranking.length) return 'Ready';
    return c?.lifetime ? 'Calculated' : 'Year 1 calculated';
  }
  if (index === 4) {
    if (!ranking.length) return 'Not available';
    return c?.economics ? 'Calculated' : 'Optional';
  }
  if (index === 5) {
    if (analysis?.status === 'CANNOT_RECOMMEND') return 'No clear winner';
    if ((d.co_leaders || []).length > 1) return 'No clear winner';
    return ranking.length ? 'Decision ready' : 'Not available';
  }
  return 'Not available';
}

function stageAllowed(index) {
  const ranking = analysis?.decision?.ranking || [];
  if (index === 0) return true;
  if (index === 1) return Boolean(site);
  if (index === 2) return Boolean(site);
  if (index === 3) return Boolean(analysis);
  if (index === 4) return Boolean(ranking.length);
  if (index === 5) return Boolean(ranking.length || analysis?.status === 'CANNOT_RECOMMEND');
  return false;
}

function stageNav() {
  const current = stageDefs.findIndex(s => s.path === route());
  return `<div class="decision-bar-wrap"><div class="decision-bar" role="navigation" aria-label="SOLARYN Decision Engine">
    <div class="decision-bar-title"><span>Decision Engine</span><small>Site → lifetime value</small></div>
    <div class="decision-stages">${stageDefs.map((s, i) => {
      const status = stageStatus(i);
      const allowed = stageAllowed(i);
      const stateClass = /calculated|retrieved|compared|selected|decision ready|year 1/i.test(status) ? 'is-done' : /unavailable|not /i.test(status) ? 'is-muted' : '';
      const inner = `<span class="stage-index">${s.n}</span><span class="stage-copy"><strong>${esc(s.name)}</strong><small>${esc(status)}</small></span>`;
      return allowed ? `<a class="decision-stage ${current === i ? 'is-current' : ''} ${stateClass}" href="${link(s.path)}" ${current === i ? 'aria-current="step"' : ''}>${inner}</a>` : `<span class="decision-stage is-disabled ${stateClass}" aria-disabled="true">${inner}</span>`;
    }).join('')}</div>
  </div></div>`;
}

function headerActions() {
  const ranked = Boolean(analysis?.decision?.ranking?.length);
  return `<div class="header-actions">
    ${adminProfile ? `<a class="account-link" href="/profile">Admin profile</a><button class="share-button" id="logout" type="button">Log out</button>` : '<a class="account-link" href="/login">Admin login</a>'}
    ${analysis ? `<a class="text-action" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/export" download>Export</a>` : ''}
    ${ranked ? `<a class="text-action" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/report?inline=true" target="_blank" rel="noopener">Report</a>` : ''}
    ${(site || analysis) ? `<a class="text-action" href="${link('evidence')}">Evidence</a>` : ''}
    <button class="share-button" id="share-prototype" type="button">Share prototype ↗</button>
    <span class="environment"><i></i> Research prototype</span>
  </div>`;
}

function shell(content) {
  const selectedLabel = site ? (placeName || 'Resolving location…') : 'No site selected';
  root.innerHTML = `<header class="app-header">
      <div class="brand-block"><a href="/" aria-label="SOLARYN Home">${SolarynLogo('compact')}</a><span class="brand-divider"></span><span class="product-name">Decision Intelligence</span></div>
      <div class="workspace-location" ${site ? '' : 'hidden'}><span class="location-kicker">Selected site</span><strong data-place-label>${esc(selectedLabel)}</strong><small data-coordinate-label>${esc(coords(site))}</small></div>
      ${headerActions()}
    </header>
    ${adminProfile && route() && !['evidence', 'login', 'profile'].includes(route()) ? stageNav() : ''}
    <main id="main" tabindex="-1">${content}<div id="error" role="alert"></div></main>
    <footer><span>SOLARYN · Climate-aware PV decision intelligence</span><span>Research prototype · Export reports to keep your results</span></footer>`;
  document.querySelector('#share-prototype').onclick = async () => {
    const control = document.querySelector('#share-prototype');
    try {
      await navigator.clipboard.writeText(location.origin + '/');
      control.textContent = 'Link copied ✓';
    } catch {
      const hint = document.createElement('div');
      hint.className = 'notice share-fallback';
      hint.setAttribute('role', 'status');
      hint.textContent = `Copy this prototype link: ${location.origin}/`;
      document.querySelector('.share-fallback')?.remove();
      document.querySelector('#main').prepend(hint);
    }
  };
  const logout = document.querySelector('#logout');
  if (logout) logout.onclick = () => action(async () => {
    await request('/auth/logout', { method: 'POST' });
    writeKey('site', null); writeKey('analysis', null);
    site = null; analysis = null; selected.clear(); adminProfile = null;
    location.assign('/');
  });
}

function loginPage() {
  return `<section class="auth-layout"><div class="auth-intro"><div class="eyebrow">SOLARYN / ADMIN ACCESS</div><h1>Your analysis<br>workspace.</h1><p>Sign in as the administrator to select sites, compare modules and review the evidence behind every decision.</p><div class="notice">Visitors can explore the homepage. Analysis tools and saved results are reserved for the admin.</div><a class="text-link" href="/">← Back to the homepage</a></div><section class="platform-card auth-card"><span class="auth-icon" aria-hidden="true">↗</span><h2>Admin login</h2><p>Enter your administrator credentials.</p><form id="login-form"><label for="username">Username</label><input id="username" name="username" autocomplete="username" required maxlength="128" autofocus><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256"><label class="show-password"><input id="show-password" type="checkbox">Show password</label><div id="login-error" role="alert"></div><button class="button" type="submit">Sign in to analysis →</button></form><small>Admin-only workspace · No public registration</small></section></section>`;
}

function bindLogin() {
  document.querySelector('#show-password').onchange = e => { document.querySelector('#password').type = e.target.checked ? 'text' : 'password'; };
  document.querySelector('#login-form').onsubmit = async e => {
    e.preventDefault();
    const submit = e.target.querySelector('button');
    const status = document.querySelector('#login-error');
    submit.disabled = true; submit.textContent = 'Signing in…'; status.textContent = '';
    try {
      await request('/auth/login', { method: 'POST', body: JSON.stringify({username: e.target.username.value.trim(), password: e.target.password.value}) });
      location.assign('/site');
    } catch (err) {
      status.textContent = err.message;
      submit.disabled = false; submit.textContent = 'Sign in to analysis →';
    }
  };
}

function profilePage() {
  return `${heading('ADMIN PROFILE', 'Your workspace access.', 'Manage analyses with your administrator profile.')}<section class="platform-card auth-card profile-card"><span class="profile-avatar">A</span><h2>${esc(adminProfile.name)}</h2>${badge('Admin', 'success')}<dl class="data-list"><dt>Username</dt><dd>${esc(adminProfile.username)}</dd><dt>Access</dt><dd>All analysis tools, saved results and exports</dd><dt>Session</dt><dd>Expires eight hours after login</dd></dl>${button('Open analysis workspace', 'site')}<p class="small">Public visitors can view the homepage only. Use Log out when you finish.</p></section>`;
}

function error(message) {
  const el = document.querySelector('#error');
  if (el) el.innerHTML = warning(message);
}

async function action(fn) {
  try { await fn(); } catch (err) { error(err.message); }
}

function placeCacheKey(lat, lon) {
  return `solaryn-place:${Number(lat).toFixed(4)},${Number(lon).toFixed(4)}`;
}

function readPlace(lat, lon) {
  try { return localStorage.getItem(placeCacheKey(lat, lon)); } catch { return null; }
}

function savePlace(lat, lon, label) {
  try { localStorage.setItem(placeCacheKey(lat, lon), label); } catch { /* presentation cache only */ }
}

async function reverseGeocode(latitude, longitude, target = 'saved') {
  const cached = readPlace(latitude, longitude);
  if (cached) {
    if (target === 'saved') placeName = cached; else draftPlaceName = cached;
    updatePlaceLabels(target);
    return cached;
  }
  geocodeController?.abort();
  geocodeController = new AbortController();
  try {
    const url = new URL('/api/v1/geocode/reverse', location.origin);
    url.searchParams.set('lat', latitude);
    url.searchParams.set('lon', longitude);
    const response = await fetch(url, { signal: geocodeController.signal, headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Reverse geocoding unavailable');
    const payload = await response.json();
    const label = payload.label || 'Location name unavailable';
    savePlace(latitude, longitude, label);
    if (target === 'saved') placeName = label; else draftPlaceName = label;
    updatePlaceLabels(target);
    return label;
  } catch (err) {
    if (err.name === 'AbortError') return null;
    const label = 'Location name unavailable';
    if (target === 'saved') placeName = label; else draftPlaceName = label;
    updatePlaceLabels(target);
    return label;
  }
}

function scheduleDraftGeocode(latitude, longitude) {
  clearTimeout(geocodeTimer);
  draftPlaceName = readPlace(latitude, longitude) || 'Resolving location…';
  updatePlaceLabels('draft');
  geocodeTimer = setTimeout(() => reverseGeocode(latitude, longitude, 'draft'), 1100);
}

function updatePlaceLabels(target = 'saved') {
  if (target === 'saved') {
    document.querySelectorAll('[data-place-label]').forEach(el => { el.textContent = placeName || 'Location name unavailable'; });
    document.querySelectorAll('[data-coordinate-label]').forEach(el => { el.textContent = coords(site); });
  } else {
    const el = document.querySelector('#selected-place');
    if (el) el.textContent = draftPlaceName || 'Location name unavailable';
  }
}

async function render() {
  const ticket = ++generation;
  if (map) { map.remove(); map = null; marker = null; }
  shell('<div class="loading"><div class="loading-bar"></div><span>Loading SOLARYN workspace…</span></div>');
  try {
    const session = await request('/auth/session');
    if (ticket !== generation) return;
    adminProfile = session.authenticated ? session.profile : null;
    if (!adminProfile) {
      site = null; analysis = null; climate = null; selected.clear();
      if (route()) {
        if (route() !== 'login') history.replaceState({}, '', '/login');
        shell(loginPage()); bindLogin(); document.title = 'SOLARYN · Admin login';
      } else {
        shell(home([])); setupMap(false); document.title = 'SOLARYN · Overview';
      }
      return;
    }
    if (route() === 'login') history.replaceState({}, '', '/profile');
    if (route() === 'profile') { shell(profilePage()); document.title = 'SOLARYN · Admin profile'; return; }
    const query = new URLSearchParams(location.search);
    const sid = query.get('site') || readKey('site');
    const aid = query.get('analysis') || readKey('analysis');
    const [loadedSite, loadedAnalysis] = await Promise.all([sid ? api.site(sid) : null, aid ? api.analysis(aid) : null]);
    if (ticket !== generation) return;
    site = loadedSite;
    analysis = loadedAnalysis && (!site || loadedAnalysis.site.id === site.id) ? loadedAnalysis : null;
    if (!site && analysis) site = analysis.site;
    placeName = site ? (readPlace(site.latitude, site.longitude) || null) : null;

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
        const [loadedCatalog, loadedFamilies, loadedClimate] = await Promise.all([api.catalog(), api.families(), site ? api.climate(site.id) : null]);
        catalog = loadedCatalog; families = loadedFamilies; climate = loadedClimate;
        if (ticket !== generation) return;
        if (!selected.size && analysis) selected = new Set(analysis.selected_modules.map(m => m.module_id));
        shell(candidatesPage()); bindCandidates(); break;
      }
      case 'processing': shell(performancePage()); bindPerformance(); break;
      case 'economics': shell(economicsPage()); bindEconomics(); break;
      case 'results':
        shell(resultsPage());
        if (analysis?.decision?.ranking?.length) {
          try {
            const visuals = await api.visuals(analysis.id);
            if (ticket === generation && document.querySelector('#decision-visuals')) document.querySelector('#decision-visuals').innerHTML = visuals.html;
          } catch (err) {
            if (ticket === generation && document.querySelector('#decision-visuals')) document.querySelector('#decision-visuals').innerHTML = warning(`Charts unavailable: ${err.message}. Saved results remain available.`);
          }
        }
        break;
      case 'evidence':
        climate = analysis ? analysis.climate_snapshot : site ? await api.climate(site.id) : null;
        if (ticket !== generation) return;
        shell(evidencePage()); break;
      default: shell(heading('404', 'Page not found', 'Return to the SOLARYN decision workspace.') + button('Open overview', ''));
    }

    document.title = `SOLARYN · ${routeTitles[route()] || 'Overview'}`;
    window.scrollTo({ top: 0, behavior: 'instant' });
    document.querySelector('#main')?.focus({ preventScroll: true });
    if (site && !placeName) reverseGeocode(site.latitude, site.longitude, 'saved');
    else if (site) updatePlaceLabels('saved');
  } catch (err) {
    if (ticket !== generation) return;
    shell(heading('WORKSPACE', 'Unable to load this view', 'Your saved records have not been changed.') + warning(err.message) + '<div class="actions"><button class="button" id="retry">Retry</button><button class="button secondary" id="reset">Start a new site</button></div>');
    document.querySelector('#retry').onclick = render;
    document.querySelector('#reset').onclick = () => { writeKey('site', null); writeKey('analysis', null); site = null; analysis = null; history.pushState({}, '', '/site'); render(); };
  }
}

function home(recent) {
  return `<section class="platform-hero">
    <div class="hero-copy"><div class="eyebrow"><span class="yellow-line"></span> SOLAR DECISIONS, GROUNDED IN EVIDENCE</div><h1>The right solar module.<br><span>For your site.</span></h1><p>Explore your site's climate, compare real PV modules, and understand the trade-offs behind every recommendation.</p>${button(adminProfile ? 'Start a site analysis' : 'Sign in to start analysis', adminProfile ? 'site' : 'login')}<div class="hero-note">Choose a location. Compare modules. Explore the evidence.</div><div class="prototype-note">Research prototype · Recommendations remain provisional.</div></div>
    <div class="hero-map platform-card"><div class="card-header"><span>Global site explorer</span><small>WGS84 coordinates</small></div><div id="map" aria-label="World map preview"></div><div class="map-caption"><span class="crosshair">⊕</span><div><strong>Every decision starts with the site.</strong><span>Select any coordinate; no predefined city list.</span></div></div></div>
  </section>
  <section class="engine-overview">${stageDefs.map(s => `<div><span>${s.n}</span><strong>${esc(s.name)}</strong></div>`).join('<b>→</b>')}</section>
  <section class="recent"><div class="section-title"><div><span class="eyebrow">EXPLORE THE WORKFLOW</span><h2>From location to a transparent decision</h2></div></div><div class="intro-grid"><article><span>01 / LOCATE</span><h3>Start anywhere</h3><p>Pick a point on the map or enter exact coordinates for your project.</p></article><article><span>02 / COMPARE</span><h3>Let the evidence lead</h3><p>Compare module-specific performance using climate data and declared assumptions.</p></article><article><span>03 / UNDERSTAND</span><h3>See why it matters</h3><p>Explore performance, optional economics, and the limits of each result.</p></article></div></section>
  ${adminProfile ? `<section class="recent"><div class="section-title"><div><span class="eyebrow">ADMIN WORKSPACE</span><h2>Recent sites</h2></div><span>Demo records may reset · Export results to keep them</span></div>${recent.length ? `<div class="recent-grid">${recent.slice(0, 3).map(s => `<a class="recent-card" href="/conditions?site=${encodeURIComponent(s.id)}"><span class="eyebrow">SAVED SITE</span><strong>${esc(readPlace(s.latitude, s.longitude) || coords(s))}</strong><span>${esc(coords(s))}</span><small>${esc(s.created_at.slice(0, 10))}</small></a>`).join('')}</div>` : '<div class="empty-inline">Your next solar decision starts here. Select a site to begin.</div>'}</section>` : '<section class="visitor-access"><strong>Analysis access is reserved for the admin.</strong><span>Explore SOLARYN here, or sign in to open the workspace.</span><a class="text-link" href="/login">Admin login →</a></section>'}`;
}

function siteAssumptionsSummary() {
  const c = analysis?.configuration;
  if (!c) return `<div class="assumption-empty"><strong>Project assumptions not finalized yet</strong><p>Technology-independent assumptions are set before the performance run.</p></div>`;
  return `<dl class="data-list"><dt>Application</dt><dd>${esc(c.application || 'Not declared')}</dd><dt>Tilt</dt><dd>${fmt(c.tilt_deg)}°</dd><dt>Azimuth</dt><dd>${fmt(c.azimuth_deg)}°</dd><dt>Albedo</dt><dd>${fmt2(c.albedo)}</dd><dt>Soiling</dt><dd>${fmt(c.soiling_pct)}%</dd><dt>Thermal model</dt><dd>Faiman U0 ${fmt(c.u0)} · U1 ${fmt(c.u1)}</dd></dl>`;
}

function sitePage() {
  return heading('01 / SITE & PROJECT', 'Define the project location.', 'Select the authoritative project coordinate. SOLARYN adds a human-readable place label without changing the scientific latitude/longitude.') +
    `<div class="site-layout"><section class="platform-card map-panel"><div class="card-header"><span>Project map</span><small>Click to select · drag to reposition</small></div><div id="map" aria-label="Interactive site selection map"></div><div id="tile-warning" role="status"></div><div class="map-bottom"><span>WGS84 · Decimal degrees</span><span>Coordinate remains authoritative</span></div></section>
    <aside class="platform-card site-panel"><div class="eyebrow">PROJECT LOCATION</div><h2 id="selected-place" data-place-label>${esc(draftPlaceName || placeName || (site ? 'Resolving location…' : 'Select a site'))}</h2><p id="selected-coordinate" class="coordinate-display">${esc(coords(site))}</p><form id="coordinate-form"><label for="latitude">Latitude <span>−90 to 90°</span></label><input id="latitude" name="latitude" type="number" step="any" min="-90" max="90" required placeholder="e.g. 50.8798" value="${site?.latitude ?? ''}"><label for="longitude">Longitude <span>−180 to 180°</span></label><input id="longitude" name="longitude" type="number" step="any" min="-180" max="180" required placeholder="e.g. 4.7005" value="${site?.longitude ?? ''}"><button class="button secondary full" type="submit">Update map <span>⊕</span></button></form><button id="continue" class="button full" ${site ? '' : 'disabled'}>Continue to Climate Fingerprint <span>→</span></button><p class="small">Place name is presentation metadata only. Provider coverage is checked during climate retrieval.</p></aside></div>
    <section class="workspace-grid two"><article class="platform-card info-card"><div class="card-header"><span>Project context</span><small>Current stored state</small></div>${siteAssumptionsSummary()}</article><article class="platform-card info-card"><div class="card-header"><span>Decision boundary</span><small>What is fixed here</small></div><div class="bullet-list"><p><strong>Coordinate:</strong> exact WGS84 latitude/longitude.</p><p><strong>Place name:</strong> reverse-geocoded display label.</p><p><strong>Project assumptions:</strong> frozen with the analysis run, never inferred from the place name.</p></div></article></section>`;
}

function setupMap(editable) {
  if (!window.L) { error('Map library unavailable. You can still enter coordinates manually.'); return; }
  map = L.map('map', { zoomControl: editable, scrollWheelZoom: editable, worldCopyJump: true, minZoom: 1, maxZoom: 18 }).setView(site ? [site.latitude, site.longitude] : [18, 0], site && editable ? 6 : 2);
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors', maxZoom: 19 }).addTo(map);
  tiles.on('tileerror', () => { const el = document.querySelector('#tile-warning'); if (el) el.textContent = 'Map tiles unavailable. Enter coordinates manually to continue.'; });
  if (editable) {
    map.on('click', event => setCoordinate(event.latlng.lat, event.latlng.wrap().lng));
    if (site) setCoordinate(site.latitude, site.longitude, false);
  }
}

function setCoordinate(latitude, longitude, geocode = true) {
  draft = { latitude, longitude };
  const lat = document.querySelector('#latitude');
  const lon = document.querySelector('#longitude');
  if (lat) lat.value = latitude;
  if (lon) lon.value = longitude;
  const selectedCoordinate = document.querySelector('#selected-coordinate');
  if (selectedCoordinate) selectedCoordinate.textContent = coords(draft);
  const continueBtn = document.querySelector('#continue');
  if (continueBtn) continueBtn.disabled = false;
  if (geocode) scheduleDraftGeocode(latitude, longitude);
  else {
    draftPlaceName = readPlace(latitude, longitude) || placeName || 'Resolving location…';
    updatePlaceLabels('draft');
  }
  if (!map) return;
  if (marker) marker.setLatLng([latitude, longitude]);
  else {
    marker = L.marker([latitude, longitude], { draggable: true, title: 'Selected site — drag to reposition', icon: L.divIcon({ className: 'site-marker', html: '<span></span>', iconSize: [26, 26], iconAnchor: [13, 13] }) }).addTo(map);
    marker.on('dragend', () => { const p = marker.getLatLng().wrap(); setCoordinate(Math.max(-90, Math.min(90, p.lat)), p.lng); });
  }
}

function bindSite() {
  draft = site ? { latitude: site.latitude, longitude: site.longitude } : null;
  draftPlaceName = site ? (readPlace(site.latitude, site.longitude) || placeName || 'Resolving location…') : null;
  updatePlaceLabels('draft');
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
      site = await api.saveSite(p); analysis = null; climate = null; selected.clear(); filters = {};
      placeName = draftPlaceName && draftPlaceName !== 'Resolving location…' ? draftPlaceName : readPlace(p.latitude, p.longitude);
      writeKey('site', site.id); writeKey('analysis', null); navigate('conditions');
    } finally { btn.disabled = false; btn.textContent = 'Continue to Climate Fingerprint →'; }
  });
}

function kpi(label, number, unit, meta = '') {
  return `<article class="kpi-card"><span>${esc(label)}</span><strong>${number}</strong><small>${esc(unit || '')}</small>${meta ? `<em>${esc(meta)}</em>` : ''}</article>`;
}

function conditionsPage() {
  if (!site) return noSite();
  const labels = {
    annual_ghi: ['Annual GHI', 'kWh/m²/year'],
    irradiance: ['Mean hourly GHI', climate?.units?.irradiance || 'W/m²'],
    air_temperature: ['Mean air temperature', climate?.units?.air_temperature || '°C'],
    relative_humidity: ['Relative humidity', climate?.units?.relative_humidity || '%'],
    wind_speed: ['Wind speed', climate?.units?.wind_speed || 'm/s'],
  };
  const metrics = climate?.metrics || {};
  return heading('02 / CLIMATE FINGERPRINT', 'Turn the coordinate into a verified climate input.', `${placeName || 'Selected site'} · ${coords(site)}`) +
    `<section class="platform-card climate-control"><div><div class="eyebrow">REFERENCE DATA</div><h2 data-place-label>${esc(placeName || 'Selected site')}</h2><p>${esc(coords(site))}</p></div><form id="climate-form"><label for="climate-year">Reference year</label><input id="climate-year" type="number" min="2005" max="${new Date().getFullYear() - 1}" value="${climate?.year}" required><button class="button" id="climate-load" type="submit">Load PVGIS + NASA POWER</button><button class="button secondary" id="climate-refresh" type="button">Refresh</button><span id="climate-progress" role="status" aria-live="polite">${climate?.id ? 'Saved snapshot' : 'Ready to retrieve hourly data'}</span></form></section>` +
    (climate?.warnings || []).map(warning).join('') +
    `<div class="kpi-grid">${Object.entries(labels).map(([key, [label, unit]]) => kpi(label, fmt(metrics[key]), unit, `${climate?.metric_sources?.[key] || 'Unavailable'} · ${climate?.period || 'No data'}`)).join('')}</div>
    <div class="workspace-grid climate-main"><section class="platform-card chart-panel"><div class="card-header"><div><span>Monthly solar resource</span><small>Horizontal GHI · kWh/m²</small></div><div class="legend"><i class="legend-pvgis"></i>PVGIS <i class="legend-nasa"></i>NASA POWER</div></div>${monthlyChart(climate)}<p class="small">Monthly bars are display scaling only; values come from the stored backend climate snapshot.</p></section>
    <section class="platform-card provenance-card"><div class="card-header"><span>Source cross-check</span>${badge(climate?.crosscheck?.status || 'Not available')}</div><dl class="data-list"><dt>PVGIS annual GHI</dt><dd>${fmt(climate?.crosscheck?.pvgis_annual_ghi_kwh_m2)} kWh/m²</dd><dt>NASA annual GHI</dt><dd>${fmt(climate?.crosscheck?.nasa_annual_ghi_kwh_m2)} kWh/m²</dd><dt>NASA vs PVGIS</dt><dd>${fmt(climate?.crosscheck?.difference_pct)}%</dd><dt>Primary source</dt><dd>${esc(climate?.provider || 'Unavailable')}</dd><dt>Reference period</dt><dd>${esc(climate?.period || 'Not retrieved')}</dd><dt>Geometry</dt><dd>Horizontal · horizon shading off</dd></dl><p class="small">${esc(climate?.crosscheck?.definition || 'Both providers must return a complete solar year for comparison.')}</p></section></div>
    <section class="provider-grid">${(climate?.providers || []).map(providerPanel).join('')}</section><div class="actions">${button('Edit Site & Project', 'site', true)}${button('Continue to Technology Behaviour', 'candidates')}</div>`;
}

function monthlyChart(snapshot) {
  const providers = snapshot?.providers || [];
  const series = providers.filter(p => p.monthly?.length);
  if (!series.length) return '<div class="chart-empty"><strong>Waiting for hourly source data</strong><p>PVGIS and NASA POWER are retrieved for the selected coordinate.</p></div>';
  const maximum = Math.max(1, ...series.flatMap(p => p.monthly.map(m => m.ghi_kwh_m2 ?? 0)));
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `<div class="resource-chart" role="img" aria-label="Monthly GHI comparison. Exact values are available below.">${months.map((name, i) => `<div class="month-group"><div class="month-bars">${['PVGIS','NASA_POWER'].map(provider => { const entry = providers.find(p => p.provider === provider)?.monthly.find(m => m.month === i + 1); const n = entry?.ghi_kwh_m2; return `<div class="resource-bar ${provider === 'PVGIS' ? 'pvgis' : 'nasa'}" style="height:${n == null ? 0 : 100 * n / maximum}%" title="${name} ${provider}: ${fmt(n)} kWh/m²"></div>`; }).join('')}</div><span>${name}</span></div>`).join('')}</div><details class="monthly-details"><summary>View exact monthly values</summary><table><thead><tr><th>Month</th><th>PVGIS · kWh/m²</th><th>NASA · kWh/m²</th></tr></thead><tbody>${months.map((name, i) => `<tr><td>${name}</td>${['PVGIS','NASA_POWER'].map(p => `<td>${fmt(providers.find(s => s.provider === p)?.monthly.find(m => m.month === i + 1)?.ghi_kwh_m2)}</td>`).join('')}</tr>`).join('')}</tbody></table></details>`;
}

function providerPanel(p) {
  return `<article class="platform-card provider-panel"><div class="card-header"><div><span>${esc(p.provider)}</span><small>${p.cache_hit ? 'Saved source reused' : 'Retrieved from provider'}</small></div>${badge(p.status)}</div>${p.error ? warning(p.error) : `<dl class="data-list"><dt>Annual GHI</dt><dd>${fmt(p.metrics?.annual_ghi)} kWh/m²</dd><dt>Solar coverage</dt><dd>${p.coverage?.valid_hours?.ghi_w_m2 ?? '—'} / ${p.coverage?.expected_hours ?? '—'} hours</dd><dt>Retrieved</dt><dd>${esc(p.retrieved_at || '—')}</dd><dt>Normalizer</dt><dd>${esc(p.normalizer_version || '—')}</dd></dl>`}<details><summary>Provenance & quality</summary>${(p.warnings || []).map(warning).join('')}<pre>${esc(JSON.stringify({ source_id: p.source_id, sha256: p.raw_sha256, coverage: p.coverage, provenance: p.provenance }, null, 2))}</pre></details>${p.source_id ? `<div class="source-downloads"><a href="/api/v1/climate-sources/${encodeURIComponent(p.source_id)}/export" download>Hourly snapshot JSON ↓</a><a href="/api/v1/climate-sources/${encodeURIComponent(p.source_id)}/export?raw=true" download>Original response ↓</a></div>` : ''}</article>`;
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
  document.querySelector('#climate-progress').textContent = 'Retrieving a full year from PVGIS and NASA POWER…';
  try {
    if (!climateRequests.has(key)) climateRequests.set(key, api.retrieveClimate(siteId, year, refresh));
    const result = await climateRequests.get(key);
    if (ticket !== generation || route() !== 'conditions' || site?.id !== siteId) return;
    climate = result; shell(conditionsPage()); bindConditions(); updatePlaceLabels('saved');
  } catch (err) {
    if (ticket === generation) { error(err.message); const progress = document.querySelector('#climate-progress'); if (progress) progress.textContent = 'Retrieval failed. You can retry.'; }
  } finally {
    climateRequests.delete(key);
    if (ticket === generation) controls.forEach(selector => { const el = document.querySelector(selector); if (el) el.disabled = false; });
  }
}

function noSite() {
  return heading('SITE REQUIRED', 'Start with Site & Project.', 'Select a coordinate before continuing through the Decision Engine.') + button('Select a site', 'site');
}

const filterFields = [['technology_family','Technology family'],['technology_subtype','Technology subtype'],['manufacturer','Manufacturer'],['monofacial_or_bifacial','Module face'],['application','Application'],['commercial_status','Commercial status'],['evidence_level','Evidence level']];
function familyMatch(m) { return filterFields.every(([key]) => !filters[key] || (m[key] || '').split('|').includes(filters[key])); }

function candidateResponse(m) {
  const row = analysis?.decision?.ranking?.find(r => r.module_id === m.module_id);
  if (!row) return `<div class="response-pending"><span>Site response</span><strong>Available after analysis</strong></div>`;
  return `<div class="candidate-response"><div><span>Year-1 DC</span><strong>${fmt(row.annual_dc_kwh_kwp)}</strong><small>kWh/kWp</small></div><div><span>Temp. contribution</span><strong>${fmt(row.contributions?.temperature_effect_kwh_kwp)}</strong><small>kWh/kWp/y</small></div><div><span>Rank</span><strong>#${row.rank}</strong><small>${esc(row.model_path || '')}</small></div></div>`;
}

function candidatesPage() {
  if (!site) return noSite();
  const toolbar = filterFields.map(([key, label]) => {
    const options = key === 'technology_family' ? families : [...new Set(catalog.modules.flatMap(m => (m[key] || '').split('|')).filter(Boolean))].sort();
    return `<label>${label}<select data-filter="${key}"><option value="">All</option>${options.map(v => `<option value="${esc(v)}" ${filters[key] === v ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></label>`;
  }).join('');
  const modules = catalog.modules.filter(familyMatch);
  return heading('03 / TECHNOLOGY BEHAVIOUR', 'Compare exact commercial candidates.', 'Filter, inspect and select exact SKUs. SOLARYN keeps technology labels separate from the numerical ranking logic.') +
    warning(catalog.warning) + `<div class="technology-layout"><aside class="platform-card filter-rail"><div class="card-header"><span>Candidate filters</span><small>${modules.length} shown</small></div>${toolbar}<button class="button secondary full" id="clear-selection">Clear selection</button><div class="selection-summary"><strong id="selection-count">${selected.size}</strong><span>selected · choose 3–10</span></div></aside>
    <section class="technology-main"><div class="section-title"><div><span class="eyebrow">EXACT SKU LIBRARY</span><h2>Module candidates</h2></div><span>${esc(placeName || coords(site))}</span></div><div class="module-grid">${modules.map(m => `<article class="platform-card module-card ${selected.has(m.module_id) ? 'is-selected' : ''}"><label class="module-select"><input type="checkbox" data-module="${esc(m.module_id)}" aria-label="Select ${esc(m.manufacturer)} ${esc(m.model)}" ${selected.has(m.module_id) ? 'checked' : ''}><span><small>${esc(m.technology_family || m.technology)}</small><strong>${esc(m.manufacturer)}</strong><span class="model">${esc(m.model)}</span></span></label><div class="module-badges">${badge(m.commercial_status)} ${badge(m.evidence_level || 'EVIDENCE')}</div><p class="architecture">${esc(m.technology_subtype || '—')} · ${esc(m.cell_architecture || '—')}</p><div class="spec-grid"><div><span>Power</span><strong>${value(m.rated_power_w)} W</strong></div><div><span>Efficiency</span><strong>${value(m.efficiency_pct)}%</strong></div><div><span>Temp. coefficient</span><strong>${value(m.temperature_coefficient_pct_per_c)} %/°C</strong></div><div><span>Bifaciality</span><strong>${value(m.bifaciality_pct)}%</strong></div></div>${candidateResponse(m)}<details><summary>Evidence & source</summary><p>${esc(m.source_note || 'No source note')}</p><p class="small">${esc(m.module_architecture || '')} · ${esc(m.application?.replaceAll('|',' / ') || 'Application not established')}</p>${m.source_url ? `<a href="${esc(m.source_url)}" target="_blank" rel="noopener noreferrer">Manufacturer source ↗</a>` : ''}</details></article>`).join('') || '<div class="platform-card empty-state"><h2>No candidates match these filters</h2><p>Adjust the evidence or technology filters.</p></div>'}</div><div class="actions"><p class="small">Site response values appear only after the backend analysis has run.</p><button class="button" id="prepare" ${selected.size < 3 ? 'disabled' : ''}>Continue to Lifetime Performance →</button></div></section></div>`;
}

function bindCandidates() {
  document.querySelectorAll('[data-filter]').forEach(input => input.onchange = () => { filters[input.dataset.filter] = input.value; shell(candidatesPage()); bindCandidates(); updatePlaceLabels('saved'); });
  document.querySelector('#clear-selection').onclick = () => { selected.clear(); shell(candidatesPage()); bindCandidates(); updatePlaceLabels('saved'); };
  document.querySelectorAll('[data-module]').forEach(input => input.onchange = () => {
    input.checked ? selected.add(input.dataset.module) : selected.delete(input.dataset.module);
    if (selected.size > 10) { selected.delete(input.dataset.module); input.checked = false; error('Select up to ten candidates.'); }
    document.querySelector('#selection-count').textContent = selected.size;
    document.querySelector('#prepare').disabled = selected.size < 3;
    input.closest('.module-card')?.classList.toggle('is-selected', input.checked);
  });
  document.querySelector('#prepare').onclick = () => action(async () => {
    const btn = document.querySelector('#prepare'); btn.disabled = true; btn.textContent = 'Freezing candidate set…';
    try { analysis = await api.analyse(site.id, [...selected]); writeKey('analysis', analysis.id); navigate('processing'); }
    finally { btn.disabled = false; btn.textContent = 'Continue to Lifetime Performance →'; }
  });
}

function performancePage() {
  if (!analysis) return heading('04 / LIFETIME PERFORMANCE', 'Select candidate technologies first.', 'A frozen candidate set is required before running performance.') + button('Open Technology Behaviour', 'candidates');
  const ranking = analysis.decision?.ranking || [];
  return heading('04 / LIFETIME PERFORMANCE', 'Model performance over the project horizon.', `${placeName || coords(analysis.site)} · same frozen climate and project assumptions for every candidate`) +
    `<div class="performance-layout"><section>${configurationForm()}</section><aside class="platform-card run-context"><div class="card-header"><span>Frozen comparison</span><small>${analysis.selected_modules.length} candidates</small></div><dl class="data-list"><dt>Site</dt><dd>${esc(placeName || coords(analysis.site))}</dd><dt>Climate source</dt><dd>${esc(analysis.climate_snapshot?.provider || 'Not available')}</dd><dt>Reference year</dt><dd>${esc(analysis.climate_snapshot?.period || 'Not available')}</dd><dt>Catalog release</dt><dd>${esc(analysis.catalog_release)}</dd><dt>Model state</dt><dd>${esc(analysis.model_path || 'Ready to run')}</dd></dl></aside></div>` +
    (ranking.length ? performanceResults() : `<section class="platform-card empty-state"><div class="eyebrow">PERFORMANCE OUTPUT</div><h2>Run the frozen comparison to populate this workspace.</h2><p>Year-1 and lifetime values will be returned by the backend. No display values are precomputed in the browser.</p></section>`) +
    `<div class="actions">${button('Back to Technology Behaviour', 'candidates', true)}${ranking.length ? button('Continue to Lifetime Economics', 'economics') : ''}</div>`;
}

function configurationForm() {
  const c = analysis.configuration || { objective: 'annual_dc', application: 'GENERAL_SCREENING', market_region: null, tilt_deg: 0, azimuth_deg: 180, albedo: 0.2, soiling_pct: 0, u0: 25, u1: 6.84, wind_factor: 1 };
  const field = (name, label, val, min, max, step = 'any') => `<label>${label}<input type="number" name="${name}" value="${val ?? ''}" min="${min}" max="${max}" step="${step}" required></label>`;
  return `<form id="run-form" class="platform-card configuration"><div class="card-header"><div><span>Project & performance assumptions</span><small>Frozen into a new immutable run</small></div>${badge('PROVISIONAL SCREENING')}</div><div class="form-section"><h3>Project definition</h3><div class="input-grid"><label>Project application<select name="application">${['GENERAL_SCREENING','ROOFTOP','UTILITY','BIPV_FACADE'].map(v => `<option value="${v}" ${(c.application || 'GENERAL_SCREENING') === v ? 'selected' : ''}>${v.replaceAll('_',' ')}</option>`).join('')}</select></label><label>Project market · country code<input name="market_region" value="${esc(c.market_region || '')}" pattern="[A-Z]{2}" maxlength="2" placeholder="BE, DZ, US…"></label><label>Ranking objective<select name="objective">${[['annual_dc','Annual DC specific energy'],['annual_ac','Annual AC specific energy'],['lifetime_dc','Lifetime DC specific energy']].map(([v,t]) => `<option value="${v}" ${c.objective === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label></div></div><div class="form-section"><h3>Geometry & shared losses</h3><div class="input-grid">${field('tilt_deg','Tilt · degrees',c.tilt_deg,0,90)}${field('azimuth_deg','Azimuth · north 0°, east 90°',c.azimuth_deg,0,359.99)}${field('albedo','Ground albedo · fraction',c.albedo,0,1)}${field('soiling_pct','Common soiling · %',c.soiling_pct,0,50)}</div></div><details class="form-section"><summary>Shared thermal assumptions</summary><p class="small">Faiman coefficients are shared screening assumptions, not product measurements.</p><div class="input-grid">${field('u0','U0 · W/m²/K',c.u0,.01,100)}${field('u1','U1 · W/m²/K per m/s',c.u1,0,30)}${field('wind_factor','Source wind multiplier',c.wind_factor,.01,2)}</div></details>
    <div class="scenario-toggle"><label class="toggle"><input type="checkbox" id="enable-life" ${c.lifetime ? 'checked' : ''}> Add a common lifetime scenario</label><fieldset id="life-fields" ${c.lifetime ? '' : 'disabled'}><div class="input-grid">${field('years','Project life · years',c.lifetime?.years,1,50,1)}${field('degradation_pct','Common annual degradation · %',c.lifetime?.degradation_pct,0,10)}</div><p class="small">This is explicitly a common scenario, not technology-specific degradation.</p></fieldset></div>
    <div class="scenario-toggle"><label class="toggle"><input type="checkbox" id="enable-ac" ${c.ac ? 'checked' : ''}> Add an AC conversion scenario</label><fieldset id="ac-fields" ${c.ac ? '' : 'disabled'}><div class="input-grid">${field('dc_ac_ratio','DC / AC ratio',c.ac?.dc_ac_ratio,.5,3)}${field('efficiency','Inverter efficiency · fraction',c.ac?.efficiency,.5,1)}${field('availability','Availability · fraction',c.ac?.availability,.01,1)}${field('curtailment','Curtailment · fraction',c.ac?.curtailment,0,.99)}</div></fieldset></div>
    <div class="form-footer"><p id="run-progress" role="status" aria-live="polite">${analysis.decision?.ranking?.length ? 'A calculated run is stored. Re-running creates a new immutable result.' : 'Ready to calculate.'}</p><button class="button" id="run-analysis">Run Lifetime Performance →</button></div></form>`;
}

function bindPerformance() {
  const form = document.querySelector('#run-form');
  if (!form) return;
  for (const name of ['life','ac']) document.querySelector(`#enable-${name}`).onchange = event => { document.querySelector(`#${name}-fields`).disabled = !event.target.checked; };
  form.onsubmit = event => { event.preventDefault(); action(async () => {
    const get = name => Number(form.elements[name].value);
    const config = Object.fromEntries(['tilt_deg','azimuth_deg','albedo','soiling_pct','u0','u1','wind_factor'].map(k => [k, get(k)]));
    config.objective = form.elements.objective.value;
    config.application = form.elements.application.value;
    config.market_region = form.elements.market_region.value || null;
    if (document.querySelector('#enable-life').checked) config.lifetime = { years: get('years'), degradation_pct: get('degradation_pct') };
    if (document.querySelector('#enable-ac').checked) config.ac = { dc_ac_ratio: get('dc_ac_ratio'), efficiency: get('efficiency'), availability: get('availability'), curtailment: get('curtailment') };
    const btn = document.querySelector('#run-analysis'), ticket = generation, requestId = analysis.id;
    btn.disabled = true; document.querySelector('#run-progress').textContent = 'Calculating the frozen hourly year for each candidate…';
    try { const result = await api.run(requestId, config); if (ticket !== generation) return; analysis = result; writeKey('analysis', analysis.id); navigate('economics'); }
    finally { btn.disabled = false; const progress = document.querySelector('#run-progress'); if (progress) progress.textContent = ''; }
  }); };
}

function lifetimeChart(rows) {
  const series = rows.filter(r => r.annual_lifetime?.length).slice(0, 3);
  if (!series.length) return `<div class="chart-empty"><strong>No lifetime scenario in this analysis</strong><p>Enable a common lifetime scenario to display the backend 25-year / project-life curve.</p></div>`;
  const allValues = series.flatMap(r => r.annual_lifetime.map(y => y.dc_kwh_kwp));
  const min = Math.min(...allValues), max = Math.max(...allValues);
  const width = 900, height = 300, pad = 34, span = Math.max(1e-9, max - min);
  const colors = ['#0c2f49','#f5b400','#6f8797'];
  const paths = series.map((r, idx) => {
    const points = r.annual_lifetime.map((y, i) => {
      const x = pad + (width - 2 * pad) * (i / Math.max(1, r.annual_lifetime.length - 1));
      const yy = height - pad - (height - 2 * pad) * ((y.dc_kwh_kwp - min) / span);
      return `${x.toFixed(1)},${yy.toFixed(1)}`;
    }).join(' ');
    return `<polyline points="${points}" fill="none" stroke="${colors[idx]}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join('');
  return `<div class="lifetime-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Backend lifetime DC specific energy curves">${paths}<line x1="${pad}" x2="${width-pad}" y1="${height-pad}" y2="${height-pad}" stroke="#dbe3e8"/><line x1="${pad}" x2="${pad}" y1="${pad}" y2="${height-pad}" stroke="#dbe3e8"/></svg><div class="chart-legend">${series.map((r, i) => `<span><i style="background:${colors[i]}"></i>#${r.rank} ${esc(r.manufacturer)} ${esc(r.model)}</span>`).join('')}</div></div>`;
}

function performanceResults() {
  const ranking = analysis.decision.ranking;
  const leader = ranking[0];
  const c = analysis.configuration || {};
  return `<section class="section-block"><div class="section-title"><div><span class="eyebrow">CALCULATED OUTPUT</span><h2>Lifetime performance</h2></div><span>${esc(analysis.model_path || '')}</span></div><div class="kpi-grid performance-kpis">${kpi('Year-1 DC', fmt(leader.annual_dc_kwh_kwp), 'kWh/kWp')}${kpi('Year-1 AC', fmt(leader.annual_ac_kwh_kwp), 'kWh/kWp')}${kpi('Lifetime DC', fmt(leader.lifetime_dc_kwh_kwp), 'kWh/kWp')}${kpi('Common degradation', c.lifetime ? fmt(c.lifetime.degradation_pct) : 'Not requested', c.lifetime ? '%/year' : '')}${kpi('Project life', c.lifetime ? fmt(c.lifetime.years) : 'Not requested', c.lifetime ? 'years' : '')}</div><div class="workspace-grid performance-main"><article class="platform-card chart-panel"><div class="card-header"><span>Performance over time</span><small>${c.lifetime ? 'Common degradation scenario' : 'Lifetime not requested'}</small></div>${lifetimeChart(ranking)}</article><article class="platform-card"><div class="card-header"><span>Lifetime ranking</span><small>Same site & assumptions</small></div><div class="compact-ranking">${ranking.slice(0, 5).map(r => `<div><span>#${r.rank}</span><strong>${esc(r.manufacturer)} ${esc(r.model)}</strong><em>${fmt(r.lifetime_dc_kwh_kwp ?? r.annual_dc_kwh_kwp)} ${r.lifetime_dc_kwh_kwp != null ? 'kWh/kWp lifetime' : 'kWh/kWp/y'}</em></div>`).join('')}</div></article></div></section>`;
}

function economicsPage() {
  const ranking = analysis?.decision?.ranking || [];
  if (!ranking.length) return heading('05 / LIFETIME ECONOMICS', 'Calculate performance first.', 'Economics is derived from the frozen performance result and supplied commercial inputs.') + button('Open Lifetime Performance', 'processing');
  const c = analysis.configuration || {};
  const e = c.economics || null;
  const leader = ranking[0];
  const ref = e ? analysis.selected_modules.find(m => m.module_id === e.reference_id) : null;
  return heading('05 / LIFETIME ECONOMICS', 'Translate performance into procurement headroom.', 'SOLARYN uses only supplied quotes, energy value and discount assumptions. This workflow does not claim full LCOE.') +
    `<div class="kpi-grid economics-kpis">${kpi('Maximum justified premium', leader.max_premium_eur_w == null ? 'Not available' : `+€${Number(leader.max_premium_eur_w).toFixed(4)}`, leader.max_premium_eur_w == null ? '' : '/W')}${kpi('Procurement headroom', leader.headroom_eur_w == null ? 'Not available' : `${leader.headroom_eur_w >= 0 ? '+' : ''}€${Number(leader.headroom_eur_w).toFixed(4)}`, leader.headroom_eur_w == null ? '' : '/W')}${kpi('Energy value', e ? `€${fmt2(e.energy_value_eur_kwh)}` : 'Not supplied', e ? '/kWh net AC' : '')}${kpi('Discount rate', e ? fmt2(e.discount_rate_pct) : 'Not supplied', e ? '%/year' : '')}${kpi('Economic reference', ref ? `${esc(ref.manufacturer)}` : 'Not supplied', ref ? esc(ref.model) : '')}</div>` +
    `<div class="economics-layout"><section>${economicsForm()}</section><aside class="platform-card economics-table"><div class="card-header"><span>Candidate economics</span><small>Backend result</small></div><div class="table-wrap"><table><thead><tr><th>Rank</th><th>Candidate</th><th>Quote</th><th>Max premium Δ€/W</th><th>Headroom</th></tr></thead><tbody>${ranking.map(r => `<tr><td>#${r.rank}</td><td><strong>${esc(r.manufacturer)}</strong><span class="model">${esc(r.model)}</span></td><td>${r.quote_eur_w == null ? unavailable('Not supplied') : `€${Number(r.quote_eur_w).toFixed(4)}/W`}</td><td>${r.max_premium_eur_w == null ? unavailable() : money(r.max_premium_eur_w)}</td><td>${r.headroom_eur_w == null ? unavailable() : money(r.headroom_eur_w)}</td></tr>`).join('')}</tbody></table></div></aside></div><div class="actions">${button('Back to Lifetime Performance', 'processing', true)}${button('Continue to Decision', 'results')}</div>`;
}

function economicsForm() {
  const c = analysis.configuration || {};
  const e = c.economics || null;
  if (!c.lifetime || !c.ac) return `<section class="platform-card configuration"><div class="card-header"><span>Commercial inputs</span>${badge('NOT READY')}</div>${warning('Economics requires both a lifetime scenario and an AC conversion scenario. Add them in Lifetime Performance, then return here.')}<a class="button" href="${link('processing')}">Configure Lifetime Performance →</a></section>`;
  const field = (name, label, val, min, max, step = 'any') => `<label>${label}<input type="number" name="${name}" value="${val ?? ''}" min="${min}" max="${max}" step="${step}" required></label>`;
  return `<form id="economics-form" class="platform-card configuration"><div class="card-header"><div><span>Commercial inputs</span><small>Supplied values only</small></div>${badge(e ? 'CALCULATED' : 'OPTIONAL')}</div><label>Decision objective<select name="objective">${[['annual_dc','Annual DC specific energy'],['annual_ac','Annual AC specific energy'],['lifetime_dc','Lifetime DC specific energy'],['procurement_headroom','Procurement headroom · €/W']].map(([v,t]) => `<option value="${v}" ${c.objective === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label><label>Economic reference<select name="reference_id" required><option value="">Choose a selected candidate</option>${analysis.selected_modules.map(m => `<option value="${esc(m.module_id)}" ${e?.reference_id === m.module_id ? 'selected' : ''}>${esc(m.manufacturer)} ${esc(m.model)}</option>`).join('')}</select></label><div class="input-grid">${field('energy_value_eur_kwh','Net AC energy value · €/kWh',e?.energy_value_eur_kwh,0,10)}${field('discount_rate_pct','Annual discount rate · %',e?.discount_rate_pct,0,30)}</div><div class="quote-list">${analysis.selected_modules.map((m, i) => `<div class="quote-row"><div><strong>${esc(m.manufacturer)}</strong><span>${esc(m.model)}</span></div>${field(`quote_${i}`,'Module quote · €/W',e?.quotes_eur_w?.[m.module_id],0,100)}${field(`cost_${i}`,'PV non-module costs · €/W',e?.incremental_cost_pv_eur_w?.[m.module_id],0,100)}</div>`).join('')}</div><p class="small">Maximum justified premium is a switching threshold against the supplied reference. This is not a full LCOE calculation.</p><div class="form-footer"><span id="econ-progress" class="small"></span><button class="button" type="submit">Calculate Lifetime Economics →</button></div></form>`;
}

function bindEconomics() {
  const form = document.querySelector('#economics-form');
  if (!form) return;
  form.onsubmit = event => { event.preventDefault(); action(async () => {
    if (!form.reportValidity()) return;
    const c = analysis.configuration;
    const get = name => Number(form.elements[name].value);
    const config = {
      objective: form.elements.objective.value,
      application: c.application,
      market_region: c.market_region,
      tilt_deg: c.tilt_deg,
      azimuth_deg: c.azimuth_deg,
      albedo: c.albedo,
      soiling_pct: c.soiling_pct,
      u0: c.u0,
      u1: c.u1,
      wind_factor: c.wind_factor,
      lifetime: c.lifetime,
      ac: c.ac,
      economics: {
        reference_id: form.elements.reference_id.value,
        energy_value_eur_kwh: get('energy_value_eur_kwh'),
        discount_rate_pct: get('discount_rate_pct'),
        quotes_eur_w: Object.fromEntries(analysis.selected_modules.map((m, i) => [m.module_id, get(`quote_${i}`)])),
        incremental_cost_pv_eur_w: Object.fromEntries(analysis.selected_modules.map((m, i) => [m.module_id, get(`cost_${i}`)])),
      },
    };
    const btn = form.querySelector('button[type=submit]'), ticket = generation, requestId = analysis.id;
    btn.disabled = true; document.querySelector('#econ-progress').textContent = 'Re-running the frozen analysis with supplied commercial inputs…';
    try { const result = await api.run(requestId, config); if (ticket !== generation) return; analysis = result; writeKey('analysis', analysis.id); navigate('results'); }
    finally { btn.disabled = false; const progress = document.querySelector('#econ-progress'); if (progress) progress.textContent = ''; }
  }); };
}

function decisionHero(d, leader) {
  const noClear = analysis.status === 'CANNOT_RECOMMEND' || (d.co_leaders || []).length > 1;
  if (analysis.status === 'CANNOT_RECOMMEND') return `<section class="decision-hero no-winner"><div><div class="eyebrow">DECISION STATUS</div><h2>No clear winner</h2><p>${esc(analysis.explanation || 'A fair comparison could not be calculated with the available candidate evidence.')}</p></div>${badge('CANNOT RECOMMEND', 'warning')}</section>`;
  if (noClear) {
    const names = (d.co_leaders || []).map(id => { const r = d.ranking.find(x => x.module_id === id); return r ? `${r.manufacturer} ${r.model}` : id; });
    return `<section class="decision-hero no-winner"><div><div class="eyebrow">NO CLEAR WINNER</div><h2>Numerical co-leaders at the current evidence resolution</h2><p>${esc(names.join(' · '))}</p><p class="small">${esc(d.tie_policy || 'No established physical preference among numerical co-leaders.')}</p></div>${badge(d.strength || 'NOT CALIBRATED', 'warning')}</section>`;
  }
  const module = moduleFor(leader.module_id);
  const technology = module?.technology_family || module?.technology || 'Technology not available';
  return `<section class="decision-hero decision-hero-premium"><div class="decision-hero-copy"><div class="eyebrow">RECOMMENDED CANDIDATE · PROVISIONAL SCREENING</div><h2>${esc(leader.manufacturer)} <span>${esc(leader.model)}</span></h2><div class="decision-meta"><span>${esc(technology)}</span><span>Strength <strong>${esc(d.strength || 'Not evaluated')}</strong></span><span>${esc(analysis.validation_status || 'Validation status unavailable')}</span></div><p>${esc(analysis.explanation || '')}</p></div><div class="decision-score"><span>#1</span><small>${esc(d.objective?.replaceAll('_', ' ') || 'objective')}</small><strong>${d.objective_unit === 'EUR/W' ? money(leader.objective_value) : `${fmt(leader.objective_value)} ${esc(d.objective_unit || '')}`}</strong></div></section>`;
}

function decisionKpis(leader) {
  if (!leader) return '';
  const lifetimeLabel = analysis?.configuration?.lifetime?.years ? `${analysis.configuration.lifetime.years}-year DC` : 'Lifetime DC';
  return `<section class="decision-kpi-grid" aria-label="Decision headline metrics">
    <article class="decision-kpi"><span>YEAR-1 DC</span><strong>${fmt(leader.annual_dc_kwh_kwp)}</strong><small>kWh/kWp</small></article>
    <article class="decision-kpi"><span>${esc(lifetimeLabel.toUpperCase())}</span><strong>${leader.lifetime_dc_kwh_kwp == null ? '—' : fmt(leader.lifetime_dc_kwh_kwp)}</strong><small>kWh/kWp</small></article>
    <article class="decision-kpi"><span>MAX JUSTIFIED PREMIUM</span><strong>${leader.max_premium_eur_w == null ? '—' : money(leader.max_premium_eur_w)}</strong><small>vs supplied reference</small></article>
    <article class="decision-kpi"><span>PROCUREMENT HEADROOM</span><strong>${leader.headroom_eur_w == null ? '—' : money(leader.headroom_eur_w)}</strong><small>after supplied quote</small></article>
  </section>`;
}

function decisionTopThree(d) {
  const rows = d.top_three || d.ranking?.slice(0, 3) || [];
  return `<section class="decision-ranking-section"><div class="section-title decision-section-title"><div><span class="eyebrow">TOP 3 · EXACT SKUs</span><h2>Ranked candidates</h2></div><span>Same frozen site, climate and assumptions</span></div><div class="decision-ranking-list">${rows.map(r => { const m = moduleFor(r.module_id); return `<article class="decision-rank-row ${r.rank === 1 ? 'is-leader' : ''}"><div class="decision-rank-number">#${r.rank}</div><div class="decision-rank-name"><span>${esc(m?.technology_family || m?.technology || 'Technology')}</span><strong>${esc(r.manufacturer)} ${esc(r.model)}</strong><small>${esc(r.model_path || '')}</small></div><div class="decision-rank-metric"><span>Year-1 DC</span><strong>${fmt(r.annual_dc_kwh_kwp)}</strong><small>kWh/kWp</small></div><div class="decision-rank-metric"><span>Lifetime DC</span><strong>${r.lifetime_dc_kwh_kwp == null ? '—' : fmt(r.lifetime_dc_kwh_kwp)}</strong><small>kWh/kWp</small></div><div class="decision-rank-metric"><span>Δ€/W max</span><strong>${r.max_premium_eur_w == null ? '—' : money(r.max_premium_eur_w)}</strong><small>${r.headroom_eur_w == null ? 'headroom unavailable' : `headroom ${money(r.headroom_eur_w)}`}</small></div></article>`; }).join('')}</div></section>`;
}

function resultsPage() {
  const ranking = analysis?.decision?.ranking || [];
  if (!analysis) return heading('06 / DECISION', 'No analysis loaded.', 'Complete the Decision Engine stages first.') + button('Start at Site & Project', 'site');
  if (analysis.status === 'CANNOT_RECOMMEND') return heading('06 / DECISION', 'The evidence does not support a winner.', `${placeName || coords(analysis.site)} · transparent failure state`) + decisionHero(analysis.decision || {}, null) + (analysis.candidate_failures || []).map(f => warning(`${f.module_id}: ${f.reason}`)).join('') + decisionTrace();
  if (!ranking.length) return heading('06 / DECISION', 'Decision not ready.', 'Run Lifetime Performance before opening the final decision.') + button('Open Lifetime Performance', 'processing');
  const d = analysis.decision, leader = ranking[0];
  const location = placeName || coords(analysis.site);
  const source = analysis.climate_snapshot?.provider || 'Climate source unavailable';
  const year = analysis.climate_snapshot?.year || '';
  return `<div class="decision-page">${heading('06 / DECISION', `Recommended technology for ${location}.`, `${source}${year ? ` · ${year}` : ''} · evidence-bounded ranking from one frozen project comparison.`)}
    ${decisionHero(d, leader)}
    ${decisionKpis(leader)}
    <div class="decision-toolbar"><div class="decision-boundary"><strong>Decision boundary</strong><span>${esc(d.strength_reason || 'Recommendation strength is constrained by the available evidence.')}</span></div>${downloadButtons()}</div>
    ${decisionTopThree(d)}
    <details class="decision-more"><summary>Why this recommendation?</summary><div class="decision-more-body"><p>${esc(analysis.explanation)}</p><p>Shared resource and soiling are not independent reasons to prefer a candidate. Technology names never determine the winner.</p></div></details>
    <details class="decision-more"><summary>View full Decision Trace</summary>${decisionTrace()}</details>
    <section id="decision-visuals" aria-label="Decision dashboard" class="decision-visuals"><p role="status">Loading saved analysis charts…</p></section>
    <div class="actions">${button('Review Lifetime Economics', 'economics', true)}${button('Inspect Evidence', 'evidence')}</div></div>`;
}

function decisionTrace() {
  if (!analysis) return '';
  const c = analysis.configuration || {};
  const snapshot = analysis.climate_snapshot || {};
  const d = analysis.decision || {};
  const ranking = d.ranking || [];
  const leader = ranking[0] || null;
  const leaderModule = leader ? moduleFor(leader.module_id) : null;
  const noClear = analysis.status === 'CANNOT_RECOMMEND' || (d.co_leaders || []).length > 1;
  const techLines = analysis.selected_modules?.slice(0, 4).map(m => `${m.manufacturer} ${m.model} · ${m.technology_family || m.technology || 'Technology'}`) || [];
  const cross = snapshot.crosscheck || {};
  return `<section class="decision-trace"><div class="section-title"><div><span class="eyebrow">DECISION TRACE</span><h2>From coordinate to decision</h2></div><span>Actual stored outputs · no hard-coded result values</span></div><div class="trace-grid">
    ${traceCard('01','Site & Project', `<strong data-place-label>${esc(placeName || 'Location name unavailable')}</strong><span>${esc(coords(analysis.site))}</span><span>${c.application ? esc(c.application.replaceAll('_',' ')) : 'Project assumptions not finalized'}</span><span>${c.tilt_deg != null ? `Tilt ${fmt(c.tilt_deg)}° · Azimuth ${fmt(c.azimuth_deg)}° · Albedo ${fmt2(c.albedo)}` : 'Geometry not available in this analysis'}</span>`, 'site')}
    ${traceCard('02','Climate Fingerprint', `<strong>${fmt(snapshot.metrics?.annual_ghi)} kWh/m²/y GHI</strong><span>${fmt(snapshot.metrics?.air_temperature)} °C mean air temperature · ${fmt(snapshot.metrics?.relative_humidity)}% RH</span><span>${fmt(snapshot.metrics?.wind_speed)} ${esc(snapshot.units?.wind_speed || 'm/s')} wind</span><span>${esc(snapshot.provider || 'Provider unavailable')} · ${esc(snapshot.period || 'Period unavailable')} · cross-check ${esc(cross.status || 'unavailable')}</span>`, 'climate')}
    ${traceCard('03','Technology Behaviour', `<strong>${analysis.selected_modules?.length || 0} exact SKUs compared</strong><span>${techLines.map(esc).join('<br>') || 'No candidates stored'}</span>${leader ? `<span>Leader temp. contribution: ${fmt(leader.contributions?.temperature_effect_kwh_kwp)} kWh/kWp/y</span><span>${esc(leader.model_path || analysis.model_path || 'Model path unavailable')}</span>` : '<span>Calculated response unavailable</span>'}`, 'technology')}
    ${traceCard('04','Lifetime Performance', leader ? `<strong>${fmt(leader.annual_dc_kwh_kwp)} kWh/kWp year-1 DC</strong><span>${leader.lifetime_dc_kwh_kwp == null ? 'Lifetime energy not requested' : `${fmt(leader.lifetime_dc_kwh_kwp)} kWh/kWp lifetime DC`}</span><span>${c.lifetime ? `Common degradation scenario · ${fmt(c.lifetime.degradation_pct)}%/year · ${c.lifetime.years} years` : 'Lifetime scenario not requested'}</span><span>Validation: ${esc(analysis.validation_status || 'Unavailable')}</span>` : '<strong>Performance calculation unavailable</strong>', 'performance')}
    ${traceCard('05','Lifetime Economics', leader && c.economics ? `<strong>${money(leader.max_premium_eur_w)} max justified premium</strong><span>${money(leader.headroom_eur_w)} procurement headroom</span><span>Quote: ${leader.quote_eur_w == null ? 'Not supplied' : `€${Number(leader.quote_eur_w).toFixed(4)}/W`}</span><span>Energy value €${fmt2(c.economics.energy_value_eur_kwh)}/kWh · discount ${fmt2(c.economics.discount_rate_pct)}%</span>` : '<strong>Not available in this analysis</strong><span>Commercial inputs were not supplied.</span>', 'economics')}
    ${traceCard('06','Decision', leader ? `<strong>${noClear ? 'No clear winner' : `${esc(leader.manufacturer)} ${esc(leader.model)}`}</strong><span>${noClear ? 'Numerical co-leaders / evidence-limited decision' : esc(leaderModule?.technology_family || leaderModule?.technology || 'Technology unavailable')}</span><span>Recommendation strength: ${esc(d.strength || 'Not evaluated')}</span><span>${esc(analysis.validation_status || 'Validation status unavailable')}</span>` : `<strong>${analysis.status === 'CANNOT_RECOMMEND' ? 'No clear winner' : 'Decision unavailable'}</strong><span>${esc(analysis.explanation || '')}</span>`, 'decision')}
  </div></section>`;
}

function traceCard(n, title, body, kind) {
  return `<article class="trace-card trace-${kind}"><div class="trace-top"><span>${n}</span><small>${esc(title)}</small></div><div class="trace-body">${body}</div></article>`;
}

function downloadButtons() {
  if (!analysis?.decision?.ranking?.length) return '';
  return `<div class="download-actions"><a class="button" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/report" download>Download EPC Report ↓</a><a class="button secondary" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/package" download>Evidence Package ↓</a><a class="text-link" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/report?inline=true" target="_blank" rel="noopener">Preview report ↗</a></div>`;
}

function evidencePage() {
  const rows = analysis?.selected_modules || [];
  return `<div class="utility-heading"><a class="back-link" href="${analysis ? link('results') : link('conditions')}">← Back to Decision Engine</a>${heading('EVIDENCE', 'Inspect the evidence chain.', 'Sources, assumptions and model limitations stay attached to the decision.')}</div>` + (analysis?.decision?.ranking?.length ? downloadButtons() : '') +
    `<div class="workspace-grid evidence-grid"><section class="platform-card"><div class="card-header"><span>Analysis provenance</span><small>Stored result metadata</small></div><dl class="data-list"><dt>Site</dt><dd>${esc(placeName || coords(site))}<br><small>${esc(coords(site))}</small></dd><dt>Climate source</dt><dd>${esc(climate?.provider || 'Not retrieved')} ${esc(climate?.period || '')}</dd><dt>Module source</dt><dd>${esc(analysis?.catalog_source || 'Repository catalog')}</dd><dt>Model path</dt><dd>${esc(analysis?.model_path || 'Not run')}</dd><dt>Model version</dt><dd>${esc(analysis?.model_version || 'Not assigned')}</dd><dt>Validation status</dt><dd>${esc(analysis?.validation_status || 'NOT_RUN')}</dd><dt>Extrapolation</dt><dd>${esc(analysis?.extrapolation || 'Not calculated')}</dd></dl></section><section class="platform-card"><div class="card-header"><span>Warnings & limitations</span><small>Must remain visible</small></div>${(analysis?.warnings || ['No completed analysis is loaded.']).map(warning).join('')}<p class="small">Software checks do not establish scientific validation.</p>${analysis ? `<a class="button secondary" href="/api/v1/analyses/${encodeURIComponent(analysis.id)}/export" download>Export frozen analysis JSON ↓</a>` : ''}</section></div>${climate?.providers?.length ? `<section class="provider-grid">${climate.providers.map(providerPanel).join('')}</section>` : ''}${analysis?.manifest ? `<section class="platform-card sources"><div class="card-header"><span>Reproducibility manifest</span><small>Immutable run metadata</small></div><pre class="manifest">${esc(JSON.stringify(analysis.manifest, null, 2))}</pre></section>` : ''}<section class="platform-card sources"><div class="card-header"><span>Selected module sources</span><small>${rows.length} candidates</small></div>${rows.length ? rows.map(m => `<div><strong>${esc(m.manufacturer)} · ${esc(m.model)}</strong><p>${esc(m.source_note || 'No source note')}</p>${m.source_url && /^https:\/\//.test(m.source_url) ? `<a href="${esc(m.source_url)}" target="_blank" rel="noopener noreferrer">Open recorded manufacturer source ↗</a>` : '<span>Source unavailable</span>'}</div>`).join('') : '<p>Select modules to inspect their source records.</p>'}</section>`;
}

render();
