import nasaMetadata from '../backend/app/photo-metadata.json';
export function nasaPhotoURL(id) {
  const parts = /^([A-Z0-9]+)-([A-Z0-9]+)-(\d+)$/.exec(id);
  return parts ? `https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission=${parts[1]}&roll=${parts[2]}&frame=${parts[3]}` : null;
}
export function enrichPhoto(photo) {
  const metadata = { ...photo.metadata };
  if (metadata.focal_length == null && nasaMetadata[photo.id]) Object.assign(metadata, nasaMetadata[photo.id]);
  return { ...photo, original_url: photo.original_url || nasaPhotoURL(photo.id), metadata };
}
