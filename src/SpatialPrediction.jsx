import PredictionSummary from './PredictionSummary';
import SatelliteComparison, { useSatelliteMatrix, sharedLogRange } from './SatelliteComparison';
import ConfidenceExplanation from './ConfidenceExplanation';
import React, { useEffect, useState } from 'react';
import { Alert, Button, Chip, Slider, Stack, Typography } from '@mui/material';
import maps from './spatial-maps.json';
import { imageSource, samplePreview } from './photoImages';
import { downloadJSON } from './api';

export const spatialIds = new Set(Object.entries(maps).filter(([,m]) => m.status === 'available').map(([id]) => id));
const names = { chlor_a: 'Chlorophyll-a', kd_490: 'Kd(490)' };
const fmt = value => Number(value).toLocaleString(undefined, { maximumSignificantDigits: 1 });
const stops = [[68,1,84], [59,82,139], [33,145,140], [94,201,98], [253,231,37]];
function color(value, low, high) {
  const position = Math.max(0, Math.min(1, (Math.log10(value)-Math.log10(low))/Math.max(1e-9, Math.log10(high/low)))) * 4;
  const i = Math.min(3, Math.floor(position)), f = position-i;
  return `rgb(${stops[i].map((v,c) => Math.round(v+f*(stops[i+1][c]-v))).join(',')})`;
}
const reasonText = {
  verified_geometry_required: 'This photo needs verified location and crop geometry to exclude land reliably.',
  insufficient_geolocation_support: 'The recorded geolocation has too little support for this regional model.',
  photo_cloud_fraction_above_3pct: 'This photo exceeds the cloud limit used to train this model.',
  hardware_fraction_above_1pct: 'Too much camera or spacecraft hardware is recorded in this crop.',
  too_few_clear_offshore_regions: 'Too few clear offshore regions remain after the quality checks.',
  unsupported_footprint: 'The footprint size or shape is outside this model’s supported range.',
  footprint_outside_training_domain: 'The footprint is larger than those used to train this regional model.',
};

export default function SpatialPrediction({photo, showMaps, metadata}) {
  const satellite = useSatelliteMatrix(photo);
  const [data,setData] = useState(null), [error,setError] = useState('');
  const [target,setTarget] = useState('chlor_a'), [selected,setSelected] = useState(null);
  const [opacity,setOpacity] = useState(70), [showLayer,setShowLayer] = useState(true), [relative,setRelative] = useState(true);
  const [imageReady,setImageReady] = useState(false), [imageFailed,setImageFailed] = useState(false);
  const entry=maps[photo.id], preview=samplePreview(photo);
  useEffect(() => {
    setData(null);setError('');setSelected(null);
    if(entry?.status !== 'available')return;
    const ctrl=new AbortController();
    fetch(entry.url,{signal:ctrl.signal}).then(async response => {
      if(!response.ok)throw new Error('The regional predictions could not be loaded.');
      const d=await response.json();
      const valid=d.photo_id===photo.id && d.input_asset_id===photo.preview?.asset_id && d.source_sha256===preview?.source_sha256 &&
        d.satellite_values_used_for_inference===false && d.regions?.length>=4 && Object.keys(names).every(t =>
          d.layers?.[t]?.values.length===d.regions.length && d.layers[t].confidence_percent.length===d.regions.length && d.layers[t].values.every(v => Number.isFinite(v)&&v>0));
      if(!valid)throw new Error('These regional predictions do not match the displayed crop.');
      setData(d);
    }).catch(e => {if(e.name !== 'AbortError')setError(e.message)});
    return () => ctrl.abort();
  },[photo.id,entry?.url]);
  const layer=data?.layers[target], values=layer?.values || [];
  const low=values.length ? Math.min(...values) : 0, high=values.length ? Math.max(...values) : 0;
  const active=selected ?? values.indexOf(high), region=data?.regions[active];
  const confidence=layer?.confidence_percent[active];
  const baseRange=relative && values.length ? [Math.log10(low),Math.log10(Math.max(high,low*1.001))] : (layer?.fixed_range || [.01,10]).map(Math.log10);
  const logRange=sharedLogRange(baseRange,satellite.data?.layers[target],relative);
  const range=logRange.map(v=>10**v);
  return <section className="spatial-prediction" aria-label="Regional model predictions">
    <Stack direction="row" sx={{justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:1,mb:1}}>
      <Typography component="h3" variant="subtitle1" fontWeight={800}>Predicted water conditions</Typography>
      <Chip size="small" label="Experimental regional model" variant="outlined" />
    </Stack>
    <PredictionSummary photo={photo} target={target} onTarget={t=>{setTarget(t);setSelected(null);}} ranges={entry?.status==='available' ? Object.fromEntries(Object.keys(names).map(t=>[t,data ? [Math.min(...data.layers[t].values),Math.max(...data.layers[t].values)] : null])) : null} rangeLabel="Predicted regional range" />
    <Typography variant="body2" color="text.secondary" sx={{ my: 1.5 }}>Prediction ranges describe assessed water regions; satellite values are quality-masked footprint means. Choose a target above to change both overlays. {relative ? 'Available overlays share a scale fitted to their values.' : 'Both overlays use the same fixed scale; values outside its limits use the endpoint colors.'}</Typography>
    <div className="comparison-row">{metadata}<section className="comparison-panel predicted-overlay" aria-label="Predicted overlay">
      <div className="comparison-panel-heading"><Typography component="h4" fontWeight={800}>{data ? 'Predicted overlay' : 'Astronaut photograph'}</Typography><Stack direction="row" sx={{gap:1,flexWrap:'wrap'}}><Button size="small" disabled={!data} variant={showLayer?'contained':'outlined'} onClick={()=>setShowLayer(true)}>Model prediction map</Button><Button size="small" variant={!showLayer?'contained':'outlined'} onClick={()=>setShowLayer(false)}>Photo only</Button></Stack></div>
    {error && <Alert severity="error">{error}</Alert>}
    <div className="evidence-stage spatial-stage" style={{aspectRatio:preview?`${preview.width}/${preview.height}`:'1',margin:0}}>
      <img src={imageSource(photo)} alt={`Astronaut photograph ${photo.id}`} onLoad={() => setImageReady(true)} onError={() => setImageFailed(true)} />
      {!imageReady && <div className="image-status" role="status">{imageFailed?'Photo unavailable':'Loading photograph…'}</div>}
      {imageReady && data && showLayer && <svg className="evidence-layer" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label={`${names[target]} regional model prediction map`}>
        {data.regions.map((r,i) => {const [x0,y0,x1,y1]=r.bounds;return <rect key={r.id} role="button" tabIndex={0}
          aria-label={`Water region ${i+1}: predicted ${names[target]} ${fmt(values[i])} ${layer.units}`}
          x={x0*1000} y={y0*1000} width={(x1-x0)*1000} height={(y1-y0)*1000} fill={color(values[i],...range)} fillOpacity={opacity/100}
          stroke={active===i?'white':'rgba(255,255,255,.18)'} strokeWidth={active===i?3:0.5} vectorEffect="non-scaling-stroke"
          onClick={() => setSelected(i)} onKeyDown={e => {if(e.key==='Enter'||e.key===' '){e.preventDefault();setSelected(i)}}}>
          <title>{fmt(values[i])} {layer.units}{layer.confidence_percent[i]!=null?` · ${fmt(layer.confidence_percent[i])}% regional confidence`:''}</title>
        </rect>})}
      </svg>}
    </div>
    {entry?.status==='available' && !data && !error && <Typography variant="body2" sx={{mt:1}}>Loading regional model predictions…</Typography>}
    {entry?.status!=='available' && <Alert severity="info" sx={{mt:2}} action={<Button onClick={showMaps}>Open model maps</Button>}>{reasonText[entry?.reason] || 'A regional map is not available for this photo.'} Whole-crop results remain in the benchmark details below.</Alert>}
    {data && <>
      {showLayer && <>
        <Stack direction="row" sx={{alignItems:'center',gap:2,mt:1}}><Typography variant="caption">Map opacity</Typography><Slider size="small" aria-label="Prediction map opacity" value={opacity} onChange={(_,v)=>setOpacity(v)} sx={{flex:1}}/><Typography variant="caption">{opacity}%</Typography></Stack>
        <div className="legend-scale"/><div className="legend-labels"><span>{fmt(range[0])}</span><span>{names[target]} · {layer.units} · log scale</span><span>{fmt(range[1])}</span></div>
        <Stack direction="row" sx={{gap:1,mb:1,flexWrap:'wrap'}}><Button size="small" variant={relative?'contained':'text'} onClick={()=>setRelative(true)}>Scale for this comparison</Button><Button size="small" variant={!relative?'contained':'text'} onClick={()=>setRelative(false)}>Same scale across photos</Button></Stack>
      </>}
      <div className="evidence-reading" aria-live="polite"><strong>{selected==null?'Highest regional estimate':`Selected water region ${active+1}`}</strong>
        <div className="regional-value">{fmt(values[active])} <small>{layer.units}</small>{confidence!=null && <span>{fmt(confidence)}% regional confidence</span>}</div>
        <p>Approximately {fmt(region.area_km2)} km². {confidence!=null?'Confidence means an estimated chance of agreement within ±25% of a regional satellite reference. This photo does not need a satellite measurement.':'This is a model estimate; no supported confidence percentage is assigned to this region.'}</p>
      </div>
      <Typography variant="body2" color="text.secondary">{data.regions.length} offshore regions assessed. Blank areas are excluded by land, coast, image-quality or resolution checks; blank does not mean zero chlorophyll or zero attenuation.</Typography>
      <ConfidenceExplanation photo={photo} regional={layer} /><details><summary>Model accuracy, coverage & export</summary><p>This model learns regional RGB patterns from satellite measurements during training. Satellite values are not used to generate this photo’s map.</p>
        <p>On {layer.evaluation.photos} test photos across {layer.evaluation.groups} scene groups, within-photo pattern error improved by {fmt(layer.evaluation.contrast_skill_vs_flat*100)}% versus a flat map. {fmt(layer.evaluation.scene_within25*100)}% of regional estimates were within ±25% of the reference, with equal weight per scene. These are aggregate results, not this region’s confidence.</p>
        {layer.evaluation.contrast_skill_95pct && <p>Improvement occurred in {layer.evaluation.positive_scene_groups} of {layer.evaluation.groups} scene groups. The 95% scene-bootstrap range for average improvement is {fmt(layer.evaluation.contrast_skill_95pct[0]*100)}% to {fmt(layer.evaluation.contrast_skill_95pct[1]*100)}%, including no improvement. Consistent benefit on new scenes has not yet been established.</p>}
        <p>{data.limitations}</p><p>Whole-crop benchmark predictions below use different models and can differ from this map. Their confidence scores do not apply to these regions.</p>
        <p className="hash">Regional model: {layer.model_id}</p><p className="hash">Input SHA-256: {data.source_sha256}</p><Button size="small" onClick={()=>downloadJSON(data,`${photo.id}-regional-predictions.json`)}>Export regional predictions</Button>
      </details>
    </>}
    </section><SatelliteComparison photo={photo} target={target} evidence={satellite} range={data ? logRange : undefined} /></div>
  </section>;
}
