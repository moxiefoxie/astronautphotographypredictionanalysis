export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
export async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}/api${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map(e => e.msg).join('; ') : body.detail;
    throw new Error(typeof detail === 'string' ? detail : `API request failed (${response.status})`);
  }
  return response.json();
}
export function downloadJSON(value, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
