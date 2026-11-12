export const geographicKeys = ['latitude', 'longitude', 'radius_km', 'south', 'north', 'west', 'east'];
export const emptyGeography = Object.fromEntries(geographicKeys.map(k => [k, '']));
const present = x => x !== '' && x != null;
export function geographicError(f) {
  const radius = ['latitude', 'longitude', 'radius_km'];
  const box = ['south', 'north', 'west', 'east'];
  for (const keys of [radius, box]) {
    if (keys.some(k => present(f[k])) && !keys.every(k => present(f[k]))) return 'Complete all coordinates for the selected area.';
  }
  for (const k of geographicKeys) {
    if (!present(f[k])) continue;
    const n = Number(f[k]), bound = ['latitude', 'north', 'south'].includes(k) ? 90 : 180;
    if (!Number.isFinite(n) || (k === 'radius_km' ? n <= 0 || n > 20016 : Math.abs(n) > bound)) return `Invalid ${k.replace('_', ' ')}.`;
  }
  if (present(f.south) && Number(f.south) > Number(f.north)) return 'South must not exceed north.';
  return '';
}
export function withinGeography(p, f) {
  if (!geographicKeys.some(k => present(f[k]))) return true;
  if (p.latitude == null || p.longitude == null) return false;
  if (present(f.south) && (p.latitude < Number(f.south) || p.latitude > Number(f.north))) return false;
  if (present(f.west)) {
    const w = Number(f.west), e = Number(f.east), lon = p.longitude;
    if (w > e ? lon < w && lon > e : lon < w || lon > e) return false;
  }
  if (present(f.radius_km)) {
    const rad = Math.PI / 180, a = p.latitude * rad, b = Number(f.latitude) * rad;
    const h = Math.sin((a-b)/2)**2 + Math.cos(a)*Math.cos(b)*Math.sin((p.longitude-Number(f.longitude))*rad/2)**2;
    if (6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h)))) > Number(f.radius_km) + 1e-8) return false;
  }
  return true;
}
