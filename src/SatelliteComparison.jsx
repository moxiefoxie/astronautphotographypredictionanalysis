import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Slider, Stack, Typography } from '@mui/material';
import index from './satellite-maps.json';
import { imageSource, samplePreview } from './photoImages';
import { downloadJSON } from './api';
import { formatMeasurement as fmt } from './format';

const names = { chlor_a: 'Chlorophyll-a', kd_490: 'Kd(490)' };
const stops = [[68,1,84],[59,82,139],[33,145,140],[94,201,98],[253,231,37]];
function Matrix({ grid, range, opacity = 1, selected, onSelect }) {
  const canvas = useRef(null), width = grid[0].length, height = grid.length;
  useEffect(() => {
    const context = canvas.current.getContext('2d'), pixels = context.createImageData(width, height);
    grid.flat().forEach((v, i) => {
      if (v == null || !Number.isFinite(v)) return;
      const t = Math.max(0, Math.min(1, (v-range[0])/(range[1]-range[0]))) * 4;
      const k = Math.min(3, Math.floor(t)), f = t-k;
      for (let c=0; c<3; c++) pixels.data[i*4+c] = Math.round(stops[k][c]+f*(stops[k+1][c]-stops[k][c]));
      pixels.data[i*4+3] = 255;
    });
    context.putImageData(pixels, 0, 0);
  }, [grid, range[0], range[1]]);
  return <><canvas ref={canvas} width={width} height={height} className="evidence-layer" style={{ opacity, imageRendering: 'pixelated' }} tabIndex={0}
    aria-label="Satellite matrix; click a cell or use arrow keys to inspect" onClick={e => {
      const r = e.currentTarget.getBoundingClientRect();
      onSelect([Math.max(0,Math.min(width-1,Math.floor((e.clientX-r.left)/r.width*width))), Math.max(0,Math.min(height-1,Math.floor((e.clientY-r.top)/r.height*height)))]);
    }} onKeyDown={e => {
      const delta = { ArrowLeft: [-1,0], ArrowRight: [1,0], ArrowUp: [0,-1], ArrowDown: [0,1] }[e.key];
      if (delta) { e.preventDefault(); const [x,y] = selected || [0,0]; onSelect([Math.max(0,Math.min(width-1,x+delta[0])),Math.max(0,Math.min(height-1,y+delta[1]))]); }
    }} />
    {selected && <svg className="evidence-layer pixel-selection" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true"><rect x={selected[0]} y={selected[1]} width="1" height="1" fill="none" stroke="white" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg>}
  </>;
}

export function useSatelliteMatrix(photo) {
  const entry = photo.native_overlay?.satellite || index[photo.id], preview = samplePreview(photo);
  const [data,setData] = useState(null), [error,setError] = useState('');
  useEffect(() => {
    if (!entry) return;
    const ctrl = new AbortController();
    fetch(entry.url, { signal: ctrl.signal }).then(async response => {
      if (!response.ok) throw new Error('Satellite matrix could not be loaded.');
      const bytes = await response.arrayBuffer();
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)), v=>v.toString(16).padStart(2,'0')).join('');
      const d = JSON.parse(new TextDecoder().decode(bytes));
      const inputMatches = entry.photo_url || (d.input_asset_id === photo.preview?.asset_id && d.source_sha256 === preview?.source_sha256);
      const references = Object.values(photo.predictions).map(p=>p.satellite).filter(Boolean);
      if (digest !== entry.sha256 || d.photo_id !== photo.id || !inputMatches || !references.some(m=>m.granule_id === d.granule_id)) throw new Error('Satellite matrix does not match this photo, crop or reference.');
      if (!ctrl.signal.aborted) setData(d);
    }).catch(e => { if (e.name !== 'AbortError' && !ctrl.signal.aborted) setError(e.message); });
    return () => ctrl.abort();
  }, [photo.id]);
  return { data, error, entry };
}

export function sharedLogRange(predictionRange, layer, relative = true) {
  const values = relative ? layer?.grid_log10.flat().filter(v => v != null && Number.isFinite(v)) || [] : [];
  const low = Math.min(predictionRange[0], ...values), high = Math.max(predictionRange[1], ...values);
  return [low, Math.max(low + .001, high)];
}

export default function SatelliteComparison({ photo, target, evidence, range: sharedRange }) {
  const { data, error, entry } = evidence;
  const preview = samplePreview(photo);
  const [opacity,setOpacity] = useState(60), [selected,setSelected] = useState(null), [ready,setReady] = useState(false), [failed,setFailed] = useState(false);
  useEffect(() => { setSelected(null); }, [target]);
  const layer = data?.layers[target], values = layer?.grid_log10.flat().filter(v => v != null && Number.isFinite(v)) || [];
  const low = values.length ? Math.min(...values) : -2, high = values.length ? Math.max(...values) : 0;
  const range = sharedRange || [low, Math.max(low+.001, high)], value = selected && layer?.grid_log10[selected[1]][selected[0]];
  const aspect = entry?.width && entry?.height ? `${entry.width}/${entry.height}` : entry?.photo_url ? '1' : preview ? `${preview.width}/${preview.height}` : '1';
  const hasReference = Object.values(photo.predictions).some(p => p.satellite);
  return <section className="comparison-panel satellite-overlay" aria-label="Satellite overlay comparison">
    <div className="comparison-panel-heading"><Typography component="h4" fontWeight={800}>Satellite overlay</Typography><Typography variant="caption">{names[target]} · measured reference</Typography></div>
    {!entry ? <Alert severity="info">{hasReference ? 'The satellite footprint values are shown above. A compatible overlay is not available for this photo.' : 'No satellite reference is available for this photograph.'}</Alert> : <>
      {error && <Alert severity="error">{error}</Alert>}
      {!data && !error && <Typography role="status">Loading satellite overlay…</Typography>}
      {data && <>
        <div className="evidence-stage" style={{ aspectRatio: aspect }}><img src={entry.photo_url || imageSource(photo)} alt={`Astronaut photograph ${photo.id} with satellite overlay`} onLoad={()=>setReady(true)} onError={()=>setFailed(true)} />
          {ready ? <Matrix grid={layer.grid_log10} range={range} opacity={opacity/100} selected={selected} onSelect={setSelected} /> : <div className="image-status">{failed?'Photograph unavailable':'Loading photograph…'}</div>}
        </div>
        <Stack direction="row" sx={{ gap: 2, alignItems: 'center', my: 1 }}><Typography variant="caption">Satellite opacity</Typography><Slider size="small" value={opacity} onChange={(_,v)=>setOpacity(v)} aria-label="Satellite photo overlay opacity" /><Typography variant="caption">{opacity}%</Typography></Stack>
        <div className="legend-scale"/><div className="legend-labels"><span>{fmt(10**range[0])}</span><span>{sharedRange ? 'Same scale as prediction' : 'Satellite scale'} · {layer.units} · log</span><span>{fmt(10**range[1])}</span></div>
        <div className="evidence-reading" role="status"><strong>{selected ? `Satellite cell ${selected[0]+1}, ${selected[1]+1}` : 'Inspect the satellite overlay'}</strong><p>{selected ? value == null ? 'No usable satellite measurement in this cell.' : `${fmt(10**value)} ${layer.units}` : 'Select a cell to see its measured value. Blank areas have no usable reference.'}</p></div>
        <Typography variant="body2" color="text.secondary">Time separation: {fmt(Math.abs(data.delta_minutes))} min. {fmt(layer.display_coverage*100)}% of display cells have retained measurements. Approximate alignment; a 32 × 32 display grid does not increase satellite resolution.</Typography>
        <details><summary>Registration, RGB matrices & source evidence</summary><p>{data.method} {data.registration}</p><p>RGB image arrays are already used by the prediction models. RGB values are not direct chlorophyll or Kd(490) measurements, and matching grid dimensions does not establish matching ground resolution or pixel accuracy.</p><p>Satellite flags: {data.mask_flags.join(', ')}. Photo-specific cloud, land and glint masks may differ.</p><p className="hash">{data.granule_id}</p><Button onClick={()=>downloadJSON({...data, original_url:photo.original_url},`${photo.id}-satellite-matrix.json`)}>Export satellite matrix</Button></details>
      </>}
    </>}
  </section>;
}
