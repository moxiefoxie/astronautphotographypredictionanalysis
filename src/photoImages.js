import { nativeEntries as native } from './nativeCatalog';
import previews from './sample-previews.json';
import { API_BASE } from './api';

export function samplePreview(photo) {
  const preview = previews[photo.id];
  // A photo can have another model-input crop in a different run/cohort.
  if (!preview || photo.preview?.asset_id !== preview.asset_id) return null;
  const predictions = Object.values(photo.predictions || {});
  return predictions.length && predictions.every(p => p.evidence?.input_asset_id === preview.asset_id && p.evidence?.image_sha256 === preview.source_sha256) ? preview : null;
}

export function thumbnailSource(id) {
  return native[id]?.assets.photo || previews[id]?.url || `${API_BASE}/api/photos/${encodeURIComponent(id)}/thumbnail`;
}

export function imageSource(photo) {
  if (photo.metadata?.input_contract === 'high-density-20261109' && native[photo.id]) return native[photo.id].assets.photo;
  return samplePreview(photo)?.url || (photo.preview?.available
    ? `${API_BASE}/api/input-assets/${photo.preview.asset_id}/image`
    : `${API_BASE}/api/photos/${encodeURIComponent(photo.id)}/thumbnail`);
}

export function imageCaption(photo) {
  return samplePreview(photo) ? 'Registered model-input crop · compressed display preview' : photo.preview?.caption;
}
