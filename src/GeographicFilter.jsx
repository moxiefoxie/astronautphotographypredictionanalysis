import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, MenuItem, Stack, TextField, Typography } from '@mui/material';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { emptyGeography, geographicError, geographicKeys } from './geography';

const hasLocation = p => [p.latitude, p.longitude].every(v => v != null && v !== '' && Number.isFinite(Number(v))) && Math.abs(Number(p.latitude)) <= 90 && Math.abs(Number(p.longitude)) <= 180;
const shapeStyle = { color: '#1769e0', weight: 2, fillOpacity: 0.1, interactive: false };

// Mount only when the disclosure is open, so Leaflet starts with real dimensions.
function LocationMap({ draft, photos, selectedId, drawing, onBox, onCorner, fitRequest }) {
  const element = useRef(null), map = useRef(null), shape = useRef(null), corner = useRef(null), start = useRef(null);
  const current = useRef({ drawing, onBox, onCorner });
  current.current = { drawing, onBox, onCorner };
  useEffect(() => {
    const m = L.map(element.current, { worldCopyJump: true, scrollWheelZoom: false }).setView([25, 10], 2);
    map.current = m;
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(m);
    m.on('click', e => {
      if (!current.current.drawing) return;
      if (!start.current) {
        start.current = e.latlng;
        corner.current = L.circleMarker(e.latlng, { radius: 5, color: '#1769e0', fillOpacity: 1, interactive: false }).addTo(m);
        current.current.onCorner(true);
        return;
      }
      const bounds = L.latLngBounds(start.current, e.latlng);
      const wrap = lon => ((lon + 180) % 360 + 360) % 360 - 180;
      const west = bounds.getWest(), east = bounds.getEast();
      current.current.onBox({ ...emptyGeography,
        south: Math.max(-90, bounds.getSouth()).toFixed(4), north: Math.min(90, bounds.getNorth()).toFixed(4),
        west: east-west >= 360 ? '-180' : wrap(west).toFixed(4), east: east-west >= 360 ? '180' : wrap(east).toFixed(4) });
    });
    m.on('mousemove', e => {
      if (!current.current.drawing || !start.current) return;
      if (shape.current) shape.current.setBounds([start.current, e.latlng]);
      else shape.current = L.rectangle([start.current, e.latlng], shapeStyle).addTo(m);
    });
    const observer = new ResizeObserver(() => m.invalidateSize());
    observer.observe(element.current);
    return () => { observer.disconnect(); m.remove(); map.current = null; shape.current = null; corner.current = null; };
  }, []);
  useEffect(() => {
    const markers = L.layerGroup().addTo(map.current);
    for (const p of photos) {
      const selected = p.id === selectedId;
      const label = document.createElement('span'); label.textContent = p.id;
      L.circleMarker([Number(p.latitude), Number(p.longitude)], {
        radius: selected ? 7 : 5, color: '#fff', weight: 2, fillColor: selected ? '#c75b12' : '#1769e0', fillOpacity: 1,
        interactive: !drawing, bubblingMouseEvents: true,
      }).bindTooltip(label).addTo(markers);
    }
    return () => markers.remove();
  }, [photos, selectedId, drawing]);
  useEffect(() => {
    if (drawing) return;
    if (photos.length) map.current.fitBounds(photos.map(p => [Number(p.latitude), Number(p.longitude)]), { padding: [35,35], maxZoom: 7 });
  }, [photos, fitRequest]);
  useEffect(() => {
    const m = map.current;
    shape.current?.remove(); shape.current = null;
    corner.current?.remove(); corner.current = null; start.current = null;
    if (drawing || geographicError(draft)) return;
    if (draft.radius_km !== '' && draft.radius_km != null) {
      shape.current = L.circle([Number(draft.latitude), Number(draft.longitude)], { ...shapeStyle, radius: Number(draft.radius_km)*1000 }).addTo(m);
    } else if (draft.south !== '' && draft.south != null) {
      let east = Number(draft.east); if (east < Number(draft.west)) east += 360;
      shape.current = L.rectangle([[Number(draft.south), Number(draft.west)], [Number(draft.north), east]], shapeStyle).addTo(m);
    }
    if (shape.current) m.fitBounds(shape.current.getBounds(), { maxZoom: 10, padding: [25,25] });
  }, [draft, drawing]);
  return <div ref={element} className={`geographic-map ${drawing ? 'selecting' : ''}`} aria-label="Geographic search map" />;
}

export default function GeographicFilter({ filters, photos = [], selectedId, onApply }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState(filters.radius_km ? 'radius' : 'box');
  const [draft, setDraft] = useState({ ...emptyGeography, ...filters });
  const [drawing, setDrawing] = useState(false), [firstCorner, setFirstCorner] = useState(false), [error, setError] = useState('');
  const [fitRequest, setFitRequest] = useState(0);
  const points = useMemo(() => photos.filter(hasLocation), [photos]);
  const appliedArea = JSON.stringify(geographicKeys.map(k => filters[k] ?? ''));
  useEffect(() => {
    const values = JSON.parse(appliedArea);
    setDraft(Object.fromEntries(geographicKeys.map((k, i) => [k, values[i]])));
    setDrawing(false); setFirstCorner(false);
  }, [appliedArea]);
  const fields = mode === 'radius' ? [['latitude','Center latitude'],['longitude','Center longitude'],['radius_km','Radius (km)']] : [['south','South latitude'],['north','North latitude'],['west','West longitude'],['east','East longitude']];
  const stopDrawing = () => { setDrawing(false); setFirstCorner(false); };
  return <details className="geographic-filter" onToggle={e => { setOpen(e.currentTarget.open); stopDrawing(); }} onKeyDown={e => { if (e.key === 'Escape') stopDrawing(); }}>
    <summary>Filter by location · radius or map bounding box{filters.radius_km || filters.south !== undefined && filters.south !== '' ? ' · active' : ''}</summary>
    {open && <>
      <Typography variant="body2" sx={{ my: 2 }}>Filter by the recorded photo center. Draw a box using two corners, or enter coordinates. A west longitude greater than east crosses the date line.</Typography>
      <div className="geographic-fields">
        <TextField select fullWidth size="small" label="Area type" value={mode} onChange={e => { setMode(e.target.value); setDraft(emptyGeography); setError(''); stopDrawing(); }}><MenuItem value="box">Bounding box</MenuItem><MenuItem value="radius">Radius</MenuItem></TextField>
        {fields.map(([key,label]) => <TextField key={key} fullWidth disabled={drawing} size="small" type="number" label={label} value={draft[key] ?? ''} onChange={e => { setError(''); setDraft(d => ({ ...d, [key]: e.target.value })); }} slotProps={{ inputLabel: { shrink: true }, htmlInput: { step: 'any' } }} />)}
      </div>
      <Stack direction="row" className="geographic-map-toolbar" sx={{ gap: 1, flexWrap: 'wrap', mb: 1 }}>
        {mode === 'box' && <Button variant={drawing ? 'contained' : 'outlined'} onClick={() => { setDrawing(!drawing); setFirstCorner(false); setError(''); }}>{drawing ? 'Cancel drawing' : 'Draw bounding box'}</Button>}
        <Button disabled={drawing || !points.length} onClick={() => setFitRequest(n => n+1)}>Fit shown photos</Button>
      </Stack>
      <Typography role="status" variant="body2" sx={{ mb: 1 }}>{drawing ? firstCorner ? 'Click the opposite corner to finish the box. Esc cancels.' : 'Click the first corner on the map. Esc cancels.' : mode === 'radius' ? 'Enter a center latitude, longitude, and radius, then apply the location filter.' : draft.south !== '' && !geographicError(draft) ? 'Box ready. Choose Apply location filter to update the results.' : 'Pan or zoom to an area, then choose Draw bounding box or enter coordinates above.'}</Typography>
      <LocationMap draft={draft} photos={points} selectedId={selectedId} drawing={drawing} onCorner={setFirstCorner} fitRequest={fitRequest} onBox={box => { setDraft(box); stopDrawing(); }} />
      <div className="geographic-map-legend"><span><i />{points.length} of {photos.length} shown photos have locations</span><span><i className="selected-photo-dot" />Selected photo</span></div>
      <Stack direction="row" sx={{ gap: 1, mt: 2, flexWrap: 'wrap' }}>
        <Button variant="contained" onClick={() => { const message = geographicError(draft); setError(message); if (!message) onApply(Object.fromEntries(geographicKeys.map(k => [k, draft[k] ?? '']))); }} disabled={drawing}>Apply location filter</Button>
        <Button onClick={() => { setDraft(emptyGeography); setError(''); stopDrawing(); onApply(emptyGeography); setFitRequest(n => n+1); }}>Clear location filter</Button>
      </Stack>
      {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
    </>}
  </details>;
}
