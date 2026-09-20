// @ts-check
/** @template T @param {string} path @param {RequestInit} [options] @returns {Promise<T>} */
export async function request(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } });
  const body = await response.json();
  if (response.status === 401 && !path.startsWith('/auth/')) {
    window.location.assign('/login');
    throw new Error('Your session has expired. Please sign in again.');
  }
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map(item => item.msg).join('; ') : 'The request is invalid. Check your inputs and try again.');
  return body;
}

export const api = {
  /** @param {string} id @returns {Promise<{html:string}>} */
  visuals: id => request(`/analyses/${encodeURIComponent(id)}/visuals`),
  /** @returns {Promise<import('./contracts').Site[]>} */
  sites: () => request('/sites'),
  /** @param {string} id @returns {Promise<import('./contracts').Site>} */
  site: id => request(`/sites/${encodeURIComponent(id)}`),
  /** @param {{latitude:number, longitude:number}} value @returns {Promise<import('./contracts').Site>} */
  saveSite: value => request('/sites', { method: 'POST', body: JSON.stringify(value) }),
  /** @param {string} id @returns {Promise<import('./contracts').Climate>} */
  climate: id => request(`/sites/${encodeURIComponent(id)}/climate-snapshot`),
  /** @param {string} id @param {number} year @param {boolean} [refresh] @returns {Promise<import('./contracts').Climate>} */
  retrieveClimate: (id, year, refresh = false) => request(`/sites/${encodeURIComponent(id)}/climate-snapshot`, { method: 'POST', body: JSON.stringify({ year, refresh }) }),
  /** @returns {Promise<import('./contracts').Catalog>} */
  catalog: () => request('/modules'),
  /** @returns {Promise<string[]>} */
  families: () => request('/technology-families'),
  /** @param {string} id @param {string[]} modules @returns {Promise<import('./contracts').Analysis>} */
  analyse: (id, modules) => request('/analyses', { method: 'POST', body: JSON.stringify({ site_id: id, module_ids: modules }) }),
  /** @param {string} id @returns {Promise<import('./contracts').Analysis>} */
  analysis: id => request(`/analyses/${encodeURIComponent(id)}`),
  /** @param {string} id @param {import('./contracts').Configuration} configuration @returns {Promise<import('./contracts').Analysis>} */
  run: (id, configuration) => request(`/analyses/${encodeURIComponent(id)}/run`, { method: 'POST', body: JSON.stringify(configuration) }),
};
