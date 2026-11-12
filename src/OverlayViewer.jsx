import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, MenuItem, Slider, Stack, TextField, Typography } from '@mui/material';
import { API_BASE, api, downloadJSON } from './api';
import { imageSource, samplePreview } from './photoImages';
const labels = { water: 'Water', land: 'Land', cloud: 'Cloud', coast: 'Coast', plume: 'Plume', glint: 'Glint', possible_bloom: 'Possible bloom', unknown: 'Unknown' };
const colors = { water: '#21b9ff', land: '#edaa53', cloud: '#f5f5ff', coast: '#fc87ba', plume: '#c18bff', glint: '#ffe35d', possible_bloom: '#8bf37e', unknown: '#a9afb9' };
const names = { chlor_a: 'Chlorophyll-a', kd_490: 'Kd(490)' };
const fmt = v => Number(v).toLocaleString(undefined, { maximumSignificantDigits: 1 });
export default function OverlayViewer({ photo, writesEnabled }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [target, setTarget] = useState(''), [opacity, setOpacity] = useState(55), [grid, setGrid] = useState(null), [probe, setProbe] = useState(null);
  const [regions, setRegions] = useState([]), [points, setPoints] = useState([]), [drawing, setDrawing] = useState(false), [category, setCategory] = useState('water');
  const [dirty, setDirty] = useState(false), [visible, setVisible] = useState(Object.keys(labels));
  const [saveOpen, setSaveOpen] = useState(false), [reviewer, setReviewer] = useState(''), [key, setKey] = useState(''), [saving, setSaving] = useState(false), [notice, setNotice] = useState('');
  const [imageReady, setImageReady] = useState(false), [imageFailed, setImageFailed] = useState(false), [imageAttempt, setImageAttempt] = useState(0);
  const [baseRevision, setBaseRevision] = useState(0);
  const requestId = useRef(null);
  useEffect(() => {
    const ctrl = new AbortController();
    api(`/photos/${encodeURIComponent(photo.id)}/overlays`, { signal: ctrl.signal }).then(d => { setData(d); setRegions(d.annotations.regions); setBaseRevision(d.annotations.revision);
      try {
        const draft = JSON.parse(localStorage.getItem(`appa-regions-${photo.id}`) || 'null');
        if (draft && draft.image_sha256 === d.image_sha256) {
          setRegions(draft.regions); setPoints(draft.points || []); setCategory(draft.category || 'water'); setDrawing(!!draft.points?.length); setBaseRevision(draft.base_revision); setDirty(true);
          setNotice('Restored your unsaved region draft from this browser.');
        }
      } catch { /* A damaged browser draft must not prevent viewing saved evidence. */ } }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => ctrl.abort();
  }, [photo.id]);
  useEffect(() => {
    if (!dirty && !points.length) return;
    const protect = e => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', protect); return () => window.removeEventListener('beforeunload', protect);
  }, [dirty, points.length]);
  useEffect(() => {
    if (!data) return;
    try {
      if (dirty || points.length) localStorage.setItem(`appa-regions-${photo.id}`, JSON.stringify({ image_sha256: data.image_sha256, base_revision: baseRevision, regions, points, category }));
      else localStorage.removeItem(`appa-regions-${photo.id}`);
    } catch { setNotice('Browser draft storage is unavailable. Export before leaving this photo.'); }
  }, [data, dirty, regions, points, category, baseRevision, photo.id]);
  const sameInput = !photo.preview?.asset_id || Object.values(photo.predictions).every(p => !p.evidence.image_sha256 || p.evidence.image_sha256 === data?.image_sha256);
  const overlay = sameInput ? data?.items.find(o => o.target === target) : null;
  const source = sameInput ? data?.items[0] : null;
  const preview = samplePreview(photo);
  const imageUrl = source ? `${API_BASE}/api/overlays/${source.id}/source.png` : imageSource(photo);
  useEffect(() => {
    setGrid(null); setProbe(null);
    if (!overlay) return;
    const ctrl = new AbortController();
    api(`/overlays/${overlay.id}/values`, { signal: ctrl.signal }).then(setGrid).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => ctrl.abort();
  }, [overlay?.id]);
  function coordinate(e) { const r = e.currentTarget.getBoundingClientRect(); return [Math.max(0, Math.min(1, (e.clientX-r.left)/r.width)), Math.max(0, Math.min(1, (e.clientY-r.top)/r.height))]; }
  function track(e) {
    if (!grid) return;
    const [x,y] = coordinate(e);
    setProbe(grid.log10_grid[Math.min(grid.height-1, Math.floor(y*grid.height))][Math.min(grid.width-1, Math.floor(x*grid.width))]);
  }
  function change(next) { setRegions(next); setDirty(true); setNotice(''); requestId.current = null; }
  function finishPolygon() {
    if (points.length < 3) return;
    change([...regions, { label: category, points }]); setPoints([]); setDrawing(false);
  }
  async function save() {
    setSaving(true); setError('');
    requestId.current ||= crypto.randomUUID();
    try {
      const saved = await api(`/photos/${encodeURIComponent(photo.id)}/annotations`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` }, body: JSON.stringify({ id: requestId.current, base_revision: baseRevision, image_sha256: data.image_sha256, reviewer, regions }) });
      setData(d => ({ ...d, annotations: saved })); setDirty(false); setBaseRevision(saved.revision); setSaveOpen(false); setKey(''); requestId.current = null; setNotice(`Review revision ${saved.revision} saved to the database.`);
    } catch (e) { setError(e.message); } finally { setSaving(false); }
  }
  function exportDraft() { downloadJSON({ photo_id: photo.id, image_sha256: data?.image_sha256, base_revision: baseRevision, coordinate_system: 'Normalized decoded image x/y; origin top left', regions, unfinished_polygon: points, status: dirty ? 'draft' : data?.annotations.status }, `${photo.id}-regions.json`); }
  const polygonPoints = p => p.map(([x,y]) => `${x*1000},${y*1000}`).join(' ');
  return <div>
    <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
      <Button size="small" variant={!target ? 'contained' : 'outlined'} onClick={() => setTarget('')}>Image</Button>
      {['chlor_a', 'kd_490'].map(t => <Button size="small" key={t} variant={target === t ? 'contained' : 'outlined'} disabled={!sameInput || !data?.items.some(o => o.target === t)} onClick={() => setTarget(t)}>{names[t]} layer</Button>)}
      {overlay && <Chip label="Experimental" color="warning" size="small" />}
    </Stack>
    {error && <Alert severity="error" sx={{ mb: 1 }} onClose={() => setError('')}>{error}</Alert>}
    <div className={`overlay-stage ${drawing ? 'drawing' : ''}`} style={{ maxWidth: source ? `${440*source.width/source.height}px` : '100%', margin: 0, minHeight: imageReady ? undefined : 280, aspectRatio: !source && preview ? `${preview.width} / ${preview.height}` : undefined }}>
      <img key={`${imageUrl}:${imageAttempt}`} src={imageAttempt ? `${imageUrl}?retry=${imageAttempt}` : imageUrl} alt={`Astronaut photograph ${photo.id}`} onLoad={() => { setImageReady(true); setImageFailed(false); }} onError={() => { setImageReady(false); setImageFailed(true); }} />
      {!imageReady && <div className="image-status" role="status">{imageFailed ? <>Photo could not be loaded.<Button size="small" onClick={() => { setImageFailed(false); setImageAttempt(n => n + 1); }}>Retry photo</Button></> : 'Loading photograph…'}</div>}
      {overlay && imageReady && <img className="heatmap-layer" src={`${API_BASE}/api/overlays/${overlay.id}/image.png`} alt={`${names[target]} experimental heatmap`} style={{ opacity: opacity/100 }} />}
      {imageReady && <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" className="region-layer" aria-label={drawing ? 'Click image points to draw a region' : 'Reviewed image regions'} onPointerMove={track} onPointerLeave={() => setProbe(null)} onClick={e => { if (drawing && points.length < 500) setPoints([...points, coordinate(e)]); }}>
        {(sameInput ? regions : []).map((r,i) => visible.includes(r.label) && <polygon key={i} points={polygonPoints(r.points)} fill={colors[r.label]} fillOpacity=".23" stroke={colors[r.label]} strokeWidth="2" vectorEffect="non-scaling-stroke"><title>{labels[r.label]} · reviewer annotation</title></polygon>)}
        {!!points.length && <polyline points={polygonPoints(points)} fill="none" stroke={colors[category]} strokeWidth="2" vectorEffect="non-scaling-stroke" />}
        {points.map(([x,y],i) => <circle key={i} cx={x*1000} cy={y*1000} r="4" fill={colors[category]} />)}
      </svg>}
    </div>
    {overlay && <div className="overlay-legend">
      <div className="legend-scale" /><div className="legend-labels"><span>{fmt(10**overlay.display_log10_range[0])}</span><span>{names[target]} · {overlay.units} · log scale</span><span>{fmt(10**overlay.display_log10_range[1])}</span></div>
      <Stack direction="row" sx={{ alignItems: 'center', gap: 2 }}><Typography variant="caption">Opacity {opacity}%</Typography><Slider size="small" aria-label="Overlay opacity" value={opacity} onChange={(_, v) => setOpacity(v)} sx={{ flex: 1 }} /></Stack>
      <Typography variant="caption">{probe == null ? 'Move over the image to inspect a retained pixel.' : `Experimental pixel estimate: ${fmt(10**probe)} ${overlay.units}`}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{overlay.limitations}</Typography>
      <details><summary>Layer provenance & export</summary><p>{overlay.width} × {overlay.height} map; {fmt(overlay.retained_fraction*100)}% retained. {overlay.scale_source}.</p><p className="hash">Model: {overlay.model_version}</p><p className="hash">Source: {overlay.image_sha256}</p><Button size="small" disabled={!grid} onClick={() => downloadJSON(grid, `${photo.id}-${target}-map.json`)}>Export pixel values & provenance</Button></details>
    </div>}
    {!data ? <Typography variant="caption">Loading spatial evidence…</Typography> : !source && <Alert severity="info" sx={{ mt: 1 }}>No compatible spatial layer is available for this model input. Predictions describe the registered region as a whole.</Alert>}
    <div className="region-editor">
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1 }}><Typography fontWeight={700}>Reviewed regions</Typography><Chip size="small" label={dirty ? 'Unsaved draft' : data?.annotations.revision ? `Review v${data.annotations.revision}` : 'Not reviewed'} /></Stack>
      <Typography variant="body2" color="text.secondary">Draw water, land, cloud, or other visible regions. These are human annotations; a possible bloom is not a confirmed detection.</Typography>
      <div className="region-toggles">{Object.entries(labels).filter(([k]) => regions.some(r => r.label === k)).map(([k,v]) => <FormControlLabel key={k} control={<Checkbox size="small" checked={visible.includes(k)} onChange={e => setVisible(e.target.checked ? [...visible,k] : visible.filter(x => x !== k))} sx={{ color: colors[k], '&.Mui-checked': { color: colors[k] } }} />} label={`${v} (${regions.filter(r => r.label === k).length})`} />)}</div>
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, mt: 1.5 }}>
        <TextField select size="small" label="Region class" value={category} disabled={drawing} onChange={e => setCategory(e.target.value)} sx={{ minWidth: 155 }}>{Object.entries(labels).map(([k,v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}</TextField>
        <Button size="small" variant="outlined" disabled={!source || !imageReady || regions.length >= 100} onClick={() => { setDrawing(!drawing); setPoints([]); }}>{drawing ? 'Cancel polygon' : 'Draw region'}</Button>
        {drawing && <><Button size="small" disabled={!points.length} onClick={() => setPoints(points.slice(0,-1))}>Undo point</Button><Button size="small" variant="contained" disabled={points.length < 3} onClick={finishPolygon}>Finish polygon ({points.length})</Button></>}
      </Stack>
      {drawing && <Typography variant="caption" sx={{ display: 'block', mt: 1 }}>Click around the region boundary, then choose Finish polygon. Avoid crossing edges.</Typography>}
      {!!regions.length && <details><summary>Edit {regions.length} region{regions.length === 1 ? '' : 's'}</summary>{(sameInput ? regions : []).map((r,i) => <div className="region-row" key={i}><span>{i+1}. {labels[r.label]} · {r.points.length} vertices</span><Button size="small" onClick={() => change(regions.filter((_,j) => i !== j))}>Remove {i+1}</Button></div>)}</details>}
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, mt: 1.5 }}><Button size="small" variant="contained" disabled={!dirty || drawing || !writesEnabled} onClick={() => { setError(''); setSaveOpen(true); }}>Save review</Button><Button size="small" disabled={!data} onClick={exportDraft}>Export regions</Button>{dirty && <Button size="small" onClick={() => { setRegions(data.annotations.regions); setBaseRevision(data.annotations.revision); setNotice(''); setDirty(false); setPoints([]); setDrawing(false); }}>Discard changes</Button>}</Stack>
      {dirty && <Typography variant="caption" color="warning.main">Draft kept in this browser. Save review to store it in the shared database.</Typography>}
      {!writesEnabled && <Typography variant="caption" color="text.secondary">Operator editing is disabled on this deployment. Existing regions can still be exported.</Typography>}
      {data?.annotations.reviewer && <Typography variant="caption">Last saved by {data.annotations.reviewer} · {new Date(data.annotations.created_at).toLocaleString()}</Typography>}
      {notice && <Alert severity="success" sx={{ mt: 1 }}>{notice}</Alert>}
    </div>
    <Dialog open={saveOpen} onClose={() => { if (!saving) { setSaveOpen(false); setKey(''); } }} maxWidth="sm" fullWidth><DialogTitle>Save reviewed regions</DialogTitle><DialogContent><Typography sx={{ mb: 2 }}>Save a new revision for {photo.id}. Earlier reviews remain in the database.</Typography><Stack spacing={2}><TextField label="Reviewer name" value={reviewer} onChange={e => { setReviewer(e.target.value); requestId.current = null; }} /><TextField label="Operator API key" type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} helperText="Used only for this save; never stored in the browser." /></Stack>{error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}</DialogContent><DialogActions><Button disabled={saving} onClick={() => { setSaveOpen(false); setKey(''); }}>Cancel</Button><Button disabled={saving || !key || !reviewer.trim()} onClick={save}>Save revision</Button></DialogActions></Dialog>
  </div>;
}
