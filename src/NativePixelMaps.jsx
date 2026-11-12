import React, { useEffect, useState } from 'react';
import { Alert, Button, Chip, Slider, Stack, Typography } from '@mui/material';
import bundle from './native-maps.json';

export const nativeMapSummary = { photos: bundle.preparation.photos, maps: bundle.photos.length,
  bins: Object.keys(bundle.preparation.geographic_bins).length };
const targets = { chlor_a: { name: 'Chlorophyll-a', units: 'mg/m³', channel: 0 },
  kd_490: { name: 'Kd(490)', units: 'm⁻¹', channel: 1 } };
const fmt = n => Number(n).toLocaleString(undefined, { maximumSignificantDigits: 1 });
const asset = url => `${import.meta.env.BASE_URL}${url.replace(/^\//, '')}`;
const location = photo => {
  const lat = photo.corners_latlon.reduce((s, p) => s + p[0], 0) / 4;
  const lon = photo.corners_latlon.reduce((s, p) => s + p[1], 0) / 4;
  return `${Math.abs(lat).toFixed(1)}°${lat < 0 ? 'S' : 'N'} · ${Math.abs(lon).toFixed(1)}°${lon < 0 ? 'W' : 'E'}`;
};

function MapDetail({ photo }) {
  const [target, setTarget] = useState('chlor_a');
  const [mode, setMode] = useState('overlay');
  const [opacity, setOpacity] = useState(80);
  const [zoom, setZoom] = useState('fit');
  const [values, setValues] = useState(null);
  const [probe, setProbe] = useState(null);
  const [error, setError] = useState('');
  const [ready, setReady] = useState({});
  const info = targets[target];
  const range = bundle.scales_log10[target];
  useEffect(() => {
    const ctrl = new AbortController();
    fetch(asset(photo.assets.values), { signal: ctrl.signal }).then(async response => {
      if (!response.ok) throw new Error('Pixel values could not be loaded. Reload this view to retry.');
      const bytes = await response.arrayBuffer();
      if (bytes.byteLength !== photo.width * photo.height * 2 * 4) throw new Error('Pixel data dimensions do not match this photo.');
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), v => v.toString(16).padStart(2, '0')).join('');
      if (digest !== photo.assets.values_sha256) throw new Error('Pixel data verification failed.');
      if (!ctrl.signal.aborted) setValues(new DataView(bytes));
    }).catch(e => { if (e.name !== 'AbortError' && !ctrl.signal.aborted) setError(e.message); });
    return () => ctrl.abort();
  }, [photo]);
  function inspect(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.min(photo.width - 1, Math.max(0, Math.floor((event.clientX - bounds.left) / bounds.width * photo.width)));
    const y = Math.min(photo.height - 1, Math.max(0, Math.floor((event.clientY - bounds.top) / bounds.height * photo.height)));
    setProbe({ x, y });
  }
  const logValue = values && probe ? values.getFloat32((info.channel * photo.width * photo.height + probe.y * photo.width + probe.x) * 4, true) : null;
  const retained = 100 * photo.valid_pixels / photo.total_pixels;
  const imageError = () => setError('A map image could not be loaded. Reload this view to retry.');
  return <main className="native-detail">
    <div className="native-detail-heading"><div><div className="eyebrow">HIGH-DENSITY DATASET · HELD-OUT PHOTO</div>
      <Typography component="h3" variant="h6" fontWeight={800}>{photo.image_id}</Typography>
      <Typography variant="body2" color="text.secondary">{location(photo)} · {photo.width} × {photo.height} photo-pixel grid</Typography></div>
      <Chip label="Full-photo inference · experimental" size="small" variant="outlined" color="warning" /></div>
    <div className="native-toolbar">
      <div className="native-control-group" aria-label="Prediction target">{Object.entries(targets).map(([key, t]) =>
        <Button key={key} variant={target === key ? 'contained' : 'outlined'} aria-pressed={target === key} onClick={() => setTarget(key)}>{t.name}</Button>)}</div>
      <div className="native-control-group" aria-label="Display mode">{[['photo', 'Photo'], ['overlay', 'Overlay'], ['prediction', 'Prediction']].map(([key, name]) =>
        <Button key={key} size="small" variant={mode === key ? 'contained' : 'text'} aria-pressed={mode === key} onClick={() => setMode(key)}>{name}</Button>)}</div>
    </div>
    {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
    <div className="native-viewport" tabIndex={0} aria-label="Scrollable native-pixel map. Zoom to inspect individual pixels.">
      <div className={`native-raster ${mode === 'prediction' ? 'native-checker' : ''}`}
        style={{ width: zoom === 'native' ? `${photo.width}px` : zoom === 'fit' ? '100%' : `${Number(zoom) * 100}%`, aspectRatio: `${photo.width}/${photo.height}` }}
        onPointerMove={inspect} onClick={inspect}>
        <img className="native-photo" src={asset(photo.assets.photo)} alt={`Registered astronaut photo ${photo.image_id}`} draggable={false}
          style={{ visibility: mode === 'prediction' ? 'hidden' : 'visible' }} onLoad={() => setReady(r => ({ ...r, photo: true }))} onError={imageError} />
        {Object.keys(targets).map(key => <img key={key} className="native-layer" src={asset(photo.assets[key])} alt={`${targets[key].name} native-pixel prediction`}
          draggable={false} style={{ visibility: key === target && mode !== 'photo' && ready.photo && ready[key] ? 'visible' : 'hidden', opacity: mode === 'overlay' ? opacity / 100 : 1 }}
          onLoad={() => setReady(r => ({ ...r, [key]: true }))} onError={imageError} />)}
        {(!ready.photo || (mode !== 'photo' && !ready[target])) && !error && <div className="image-status" role="status">Loading map images…</div>}
      </div>
    </div>
    <div className="native-view-controls"><div className="native-control-group">{[['fit', 'Fit'], ['native', '1:1 pixels'], ['2', '2×'], ['4', '4×']].map(([key, name]) =>
      <Button key={key} size="small" variant={zoom === key ? 'outlined' : 'text'} aria-pressed={zoom === key} onClick={() => setZoom(key)}>{name}</Button>)}</div>
      {mode === 'overlay' && <div className="native-opacity"><Typography variant="caption">Opacity</Typography><Slider size="small" aria-label="Native map opacity" value={opacity} onChange={(_, value) => setOpacity(value)} /><span>{opacity}%</span></div>}</div>
    {mode !== 'photo' && <div className="native-legend"><div className="legend-scale" /><div className="legend-labels"><span>{fmt(10 ** range[0])}</span><span>{info.name} · {info.units} · logarithmic scale</span><span>{fmt(10 ** range[1])}</span></div>
      <Typography variant="caption" color="text.secondary">Same scale across all six photos. Purple = lower; yellow = higher. Values outside the scale use its end colours.</Typography></div>}
    <div className="native-reading" role="status"><strong>{probe ? `Pixel ${probe.x + 1}, ${probe.y + 1}` : 'Inspect a photo pixel'}</strong><span>
      {!values ? (error ? 'Pixel values unavailable.' : 'Loading verified pixel values…') : !probe ? 'Move or tap on the map to read its model estimate.' : Number.isFinite(logValue) ? `${fmt(10 ** logValue)} ${info.units} · model estimate` : 'Excluded area · no displayed prediction'}</span></div>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{fmt(retained)}% of this grid passes a pixel-by-pixel offshore and RGB screen. Transparent areas are excluded, not zero. The model processes the whole photo in one pass; there is no stitched tile grid or output smoothing.</Typography>
    <details><summary>Evaluation, limitations & downloads</summary>
      <p>Trained on 60 photos; selected using 15 validation photos; evaluated on 25 test photos across 20 independent scene groups. All six displayed photos are from the held-out test set.</p>
      <table className="comparison-table"><thead><tr><th>Regional test error (log10 MAE)</th><th>Pixel model, pooled</th><th>Constant baseline</th></tr></thead><tbody>{bundle.metrics.map(m => <tr key={m.target}><td>{targets[m.target].name}</td><td>{m.test_group_log_mae.toFixed(3)}</td><td>{m.constant_group_log_mae.toFixed(3)}</td></tr>)}</tbody></table>
      <p>These scores were recomputed using full-photo inference on the same 25 held-out photos. They describe regional aggregates, not fine-scale physical accuracy. Rectification interpolates the original photo. The pixel mask is a new heuristic, not a validated cloud or hardware detector. Pixel confidence is uncalibrated. Hardware-obstruction review is pending.</p>
      <p>Full-photo inference removes patch seams but increases regional error versus the original region-wise evaluation: {bundle.metrics.map(m => `${targets[m.target].name} ${m.original_region_inference_log_mae?.toFixed(3)} → ${m.test_group_log_mae.toFixed(3)}`).join('; ')}. Model weights and the test split are unchanged.</p>
      <p>Satellite reference values were used for training, not to generate these maps. Outputs use a frozen ConvNeXt encoder with a trained decoder and native RGB features.</p>
      <p className="hash">Checkpoint SHA-256: {bundle.checkpoint_sha256}</p>
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}><Button href={asset(photo.assets.download)} download>Download pixel arrays (.npz)</Button><Button href={asset(photo.assets[target])} download>Download map PNG</Button><Button href={asset('/native-maps/index.json')} download>Download provenance</Button></Stack>
    </details>
  </main>;
}

export default function NativePixelMaps() {
  const [selected, setSelected] = useState(bundle.photos[0].image_id);
  const photo = bundle.photos.find(p => p.image_id === selected);
  return <section aria-label="High-density native-pixel maps">
    <Alert severity="info" sx={{ mb: 2 }}>One estimate per registered photo pixel. Fine-scale accuracy is not validated; these maps are for research review.</Alert>
    <div className="native-workspace"><aside className="native-sidebar"><div className="eyebrow">SIX HELD-OUT SCENES</div>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>A geographic sample from the 100-photo high-density run.</Typography>
      <div className="native-scene-list">{bundle.photos.map(p => <button key={p.image_id} className={`native-scene ${selected === p.image_id ? 'selected' : ''}`} aria-pressed={selected === p.image_id} onClick={() => setSelected(p.image_id)}>
        <img src={asset(p.assets.photo)} alt="" loading="lazy" /><span><strong>{p.image_id}</strong><small>{location(p)}</small><small>{p.width} × {p.height} pixels</small></span>
      </button>)}</div>
      <p className="native-subset-note">100 photos · 11 geographic bins<br />400 supervised regions<br />6 exported maps · 2 targets</p>
    </aside><MapDetail key={photo.image_id} photo={photo} /></div>
  </section>;
}
