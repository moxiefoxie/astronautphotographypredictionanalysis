import bundle from './native-maps.json';
import pilot from './native-photo-catalog.json';
import { enrichPhoto } from './photoMetadata';
import { withinGeography } from './geography';

export const nativeEntries = Object.fromEntries(bundle.photos.map(p => [p.image_id, p]));
const summaries = {};
const detailCache = new Map();
let catalogRequest;
const base = (import.meta.env.VITE_NATIVE_CATALOG_BASE || (import.meta.env.DEV ? '/native-scaleup' : '')).replace(/\/$/, '');

export async function loadNativeCatalog({ refresh = false } = {}) {
  if (!base) throw new Error('The latest photo catalog is not configured.');
  if (catalogRequest && !refresh) return catalogRequest;
  catalogRequest = fetch(`${base}/index.json`, { cache:'no-cache' }).then(async r => {
    if (r.status === 404) throw new Error('The latest photo catalog is unavailable.');
    if (!r.ok) throw new Error('Expanded overlay catalog could not be loaded.');
    const data = await r.json();
    if (data.schema !== 'appa-native-catalog-v1' || !Array.isArray(data.photos)) throw new Error('Unrecognized overlay catalog.');
    for (const id of Object.keys(summaries)) delete summaries[id];
    for (const p of data.photos) { summaries[p.id] = p; nativeEntries[p.id] = p.entry; }
    return data.run;
  });
  try { return await catalogRequest; } catch (e) { catalogRequest = null; throw e; }
}
export async function loadNativeRun(signal) {
  if (!base) return null;
  const r = await fetch(`${base}/run.json`, { signal,cache:'no-cache' });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error('Overlay run status could not be loaded.');
  return r.json();
}
export function nativePhotoList(filters) {
  const items = Object.values(summaries).filter(p => withinGeography(p, filters) && withinSatelliteError(p.entry?.satellite_agreement, filters) &&
    (!filters.q || p.id.includes(filters.q.toUpperCase())) && (!filters.mission || p.mission === filters.mission) &&
    (!filters.split || p.split === filters.split) && filters.satellite !== 'false' && filters.prediction !== 'false' &&
    (!filters.start || p.captured_at.slice(0,10) >= filters.start) && (!filters.end || p.captured_at.slice(0,10) <= filters.end));
  items.sort((a,b) => (filters.sort === 'oldest' ? 1 : -1) * a.captured_at.localeCompare(b.captured_at) || a.id.localeCompare(b.id));
  return { items, total: items.length };
}
export async function loadNativePhoto(id, signal) {
  const entry = nativeEntries[id];
  if (!entry?.detail_url) {
    if (pilot[id]) return enrichPhoto(pilot[id]);
    throw new Error('Photo is not in the native overlay catalog.');
  }
  if (detailCache.has(entry.detail_url)) return detailCache.get(entry.detail_url);
  const response = await fetch(entry.detail_url,{signal});
  if (!response.ok) throw new Error('Photo metadata could not be loaded.');
  const bytes = await response.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
  const data = JSON.parse(new TextDecoder().decode(bytes));
  if (digest !== entry.detail_sha256 || data.id !== id) throw new Error('Photo metadata checksum mismatch.');
  const photo = enrichPhoto(data);
  if (detailCache.size >= 100) detailCache.delete(detailCache.keys().next().value);
  detailCache.set(entry.detail_url,photo);
  return photo;
}

export function withinSatelliteError(agreement, filters) {
  if (filters.maxError == null || filters.maxError === '') return true;
  const limit = Number(filters.maxError);
  if (!Number.isFinite(limit) || limit < 0) return false;
  const targets = !filters.errorTarget || filters.errorTarget === 'both' ? ['chlor_a', 'kd_490'] : [filters.errorTarget];
  return targets.every(target => {
    const value = agreement?.targets?.[target]?.mean_absolute_percentage_error;
    return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= limit;
  });
}
