import { api } from './api';
import { enrichPhoto } from './photoMetadata';

export async function collectSearch(filters, photoIds, onProgress = () => {}) {
  const items = [], seen = new Set();
  let total;
  for (let offset = 0; ; offset += 100) {
    const query = new URLSearchParams(Object.entries({ ...filters, offset, limit: 100 }).filter(([,v]) => v !== '' && v != null));
    if (photoIds) query.set('photo_ids', [...photoIds].join(','));
    const page = await api(`/photos?${query}`);
    if (total !== undefined && total !== page.total) throw new Error('Search results changed during export. Please retry.');
    total = page.total;
    for (const item of page.items) {
      if (seen.has(item.id)) throw new Error('Search order changed during export. Please retry.');
      seen.add(item.id); items.push(item);
    }
    onProgress(`Found ${items.length} of ${total} photos`);
    if (items.length >= total) return items;
    if (!page.items.length) throw new Error('Search export stopped before all results were received. Please retry.');
  }
}
export async function collectAnalyses(ids, localPhotos, onProgress = () => {}) {
  const output = [];
  for (let index = 0; index < ids.length; index += 4) {
    const batch = await Promise.all(ids.slice(index, index + 4).map(id => typeof localPhotos === 'function' ? localPhotos(id) : localPhotos[id] || api(`/photos/${encodeURIComponent(id)}`)));
    output.push(...batch.map(enrichPhoto));
    onProgress(`Prepared ${output.length} of ${ids.length} analyses`);
  }
  return output;
}
