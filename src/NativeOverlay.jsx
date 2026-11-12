import SatelliteAgreement from './SatelliteAgreement';
import PredictionSummary from './PredictionSummary';
import SatelliteComparison, { useSatelliteMatrix, sharedLogRange } from './SatelliteComparison';
import ConfidenceExplanation from './ConfidenceExplanation';
import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Chip, Slider, Stack, Typography } from '@mui/material';
import bundle from './native-maps.json';

import { nativeEntries } from './nativeCatalog';
const names = { chlor_a:'Chlorophyll-a', kd_490:'Kd(490)' };
const units = { chlor_a:'mg/m³', kd_490:'m⁻¹' };
const stops = [[68,1,84],[59,82,139],[33,145,140],[94,201,98],[253,231,37]];
const fmt = n => Number(n).toLocaleString(undefined,{maximumSignificantDigits:1});

export default function NativeOverlay({photo, metadata}) {
  const satellite = useSatelliteMatrix(photo);
  const entry = nativeEntries[photo.id], canvas = useRef(null);
  const [data,setData]=useState(null), [error,setError]=useState(''), [target,setTarget]=useState('chlor_a');
  const [opacity,setOpacity]=useState(70), [showLayer,setShowLayer]=useState(true), [relative,setRelative]=useState(true);
  const [selected,setSelected]=useState(null), [ready,setReady]=useState(false);
  useEffect(() => {
    const ctrl=new AbortController();
    fetch(entry.assets.values,{signal:ctrl.signal}).then(async r => {
      if(!r.ok)throw new Error('Pixel overlay could not be loaded.');
      const bytes=await r.arrayBuffer();
      if(bytes.byteLength!==entry.width*entry.height*8)throw new Error('Overlay dimensions do not match this photo.');
      const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
      if(digest!==entry.assets.values_sha256)throw new Error('Overlay checksum mismatch.');
      const view=new DataView(bytes), layers={};
      Object.keys(names).forEach((t,j)=>{
        const values=new Float32Array(entry.width*entry.height); let low=Infinity,high=-Infinity,maxIndex=null;
        for(let i=0;i<values.length;i++) { const v=view.getFloat32((j*values.length+i)*4,true);values[i]=v;
          if(Number.isFinite(v)){low=Math.min(low,v);if(v>high){high=v;maxIndex=i;}} }
        layers[t]={values,low,high,maxIndex};
      });
      if(!ctrl.signal.aborted)setData(layers);
    }).catch(e=>{if(e.name!=='AbortError'&&!ctrl.signal.aborted)setError(e.message)});
    return ()=>ctrl.abort();
  },[entry]);
  const layer=data?.[target];
  const range=sharedLogRange(relative&&layer?[layer.low,Math.max(layer.high,layer.low+.001)]:bundle.scales_log10[target], satellite.data?.layers[target], relative);
  useEffect(()=>{
    if(!layer||!canvas.current)return;
    const context=canvas.current.getContext('2d'), pixels=context.createImageData(entry.width,entry.height);
    layer.values.forEach((v,i)=>{
      if(!Number.isFinite(v))return;
      const position=Math.max(0,Math.min(1,(v-range[0])/(range[1]-range[0])))*4;
      const k=Math.min(3,Math.floor(position)), f=position-k;
      for(let c=0;c<3;c++)pixels.data[i*4+c]=Math.round(stops[k][c]+f*(stops[k+1][c]-stops[k][c]));
      pixels.data[i*4+3]=255;
    });
    context.putImageData(pixels,0,0);
  },[layer,range[0],range[1],entry]);
  const active=selected??layer?.maxIndex, value=layer?.values[active];
  function inspect(e){const r=e.currentTarget.getBoundingClientRect();const x=Math.max(0,Math.min(entry.width-1,Math.floor((e.clientX-r.left)/r.width*entry.width)));const y=Math.max(0,Math.min(entry.height-1,Math.floor((e.clientY-r.top)/r.height*entry.height)));setSelected(y*entry.width+x);}
  return <section className="spatial-prediction" aria-label="Pixel model predictions">
    <Stack direction="row" sx={{justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:1,mb:1}}><Typography component="h3" variant="subtitle1" fontWeight={800}>Predicted water conditions</Typography><Chip size="small" label="Experimental pixel model" variant="outlined" /></Stack>
    <div data-tour="predictions"><PredictionSummary photo={photo} target={target} onTarget={t=>{setTarget(t);setSelected(null);}} ranges={Object.fromEntries(Object.keys(names).map(t=>[t,data ? [10**data[t].low,10**data[t].high] : null]))} rangeLabel="Predicted pixel range" /><SatelliteAgreement agreement={entry.satellite_agreement} /></div>
    <Typography variant="body2" color="text.secondary" sx={{ my: 1.5 }}>Prediction ranges describe assessed water pixels; satellite values are quality-masked footprint means. Choose a target above to change both overlays. {relative ? 'Both overlays share a scale fitted to the prediction and satellite values.' : 'Both overlays use the same fixed scale; values outside its limits use the endpoint colors.'}</Typography>
    <div className="comparison-row" data-tour="overlays">{metadata}<section className="comparison-panel predicted-overlay" aria-label="Predicted overlay">
      <div className="comparison-panel-heading"><Typography component="h4" fontWeight={800}>Predicted overlay</Typography><Stack direction="row" sx={{gap:1,flexWrap:'wrap'}}><Button size="small" variant={showLayer?'contained':'outlined'} onClick={()=>setShowLayer(true)}>Model prediction map</Button><Button size="small" variant={!showLayer?'contained':'outlined'} onClick={()=>setShowLayer(false)}>Photo only</Button></Stack></div>
    {error&&<Alert severity="error">{error}</Alert>}
    <div className="evidence-stage spatial-stage" style={{aspectRatio:`${entry.width}/${entry.height}`,margin:0}}>
      <img src={entry.assets.photo} alt={`Astronaut photograph ${photo.id}`} onLoad={()=>setReady(true)} onError={()=>setError('Photo unavailable.')} />
      {!ready&&!error&&<div className="image-status" role="status">Loading photograph…</div>}
      <canvas ref={canvas} width={entry.width} height={entry.height} className="evidence-layer" aria-label={`${names[target]} native-pixel prediction map`} tabIndex={0}
        onClick={inspect} onKeyDown={e=>{const delta={ArrowLeft:-1,ArrowRight:1,ArrowUp:-entry.width,ArrowDown:entry.width}[e.key];if(delta){e.preventDefault();setSelected(Math.max(0,Math.min(entry.width*entry.height-1,(active??0)+delta)))}}}
        style={{visibility:ready&&data&&showLayer?'visible':'hidden',opacity:opacity/100,imageRendering:'pixelated',cursor:'crosshair'}} />
    </div>
    {data&&<>{showLayer&&<><Stack direction="row" sx={{alignItems:'center',gap:2,mt:1}}><Typography variant="caption">Map opacity</Typography><Slider size="small" aria-label="Prediction map opacity" value={opacity} onChange={(_,v)=>setOpacity(v)} sx={{flex:1}}/><Typography variant="caption">{opacity}%</Typography></Stack>
      <div className="legend-scale"/><div className="legend-labels"><span>{fmt(10**range[0])}</span><span>{names[target]} · {units[target]} · log scale</span><span>{fmt(10**range[1])}</span></div>
      <Stack direction="row" sx={{gap:1,mb:1,flexWrap:'wrap'}}><Button size="small" variant={relative?'contained':'text'} onClick={()=>setRelative(true)}>Scale for this comparison</Button><Button size="small" variant={!relative?'contained':'text'} onClick={()=>setRelative(false)}>Same scale across photos</Button></Stack></>}
      <div className="evidence-reading" aria-live="polite"><strong>{selected==null?'Highest pixel estimate':`Selected pixel ${(active%entry.width)+1}, ${Math.floor(active/entry.width)+1}`}</strong><div className="regional-value">{Number.isFinite(value)?<>{fmt(10**value)} <small>{units[target]}</small></>:'Excluded area'}</div><p>{Number.isFinite(value)?'Model estimate; pixel confidence is not calibrated.':'No displayed prediction. Blank does not mean zero.'}</p></div>
      <Typography variant="body2" color="text.secondary">{entry.width} × {entry.height} native-pixel output. Offshore and RGB screening retain {fmt(100*entry.valid_pixels/entry.total_pixels)}%. Fine-scale physical accuracy is not validated.</Typography>
      {entry.run_id && <Alert severity="info" sx={{mt:1}}>Expanded inference · {entry.pixel_model_exposure?.replaceAll('_', ' ')}. This collection includes training, validation, and test photos; it is not a new held-out accuracy evaluation.</Alert>}
      <ConfidenceExplanation photo={photo} pixel /><details><summary>Model accuracy, coverage & export</summary><p>Single full-photo inference with pixel-level masking. No stitched blocks or output smoothing. {entry.run_id ? 'This expanded run uses the frozen pixel model; its performance must be assessed separately by scene group.' : <>Regional test log10 MAE: {bundle.metrics.map(m=>`${names[m.target]} ${fmt(m.test_group_log_mae)} (original region-wise inference ${fmt(m.original_region_inference_log_mae)})`).join('; ')}. Evaluated on the same 25 held-out photos; not a validation of individual pixels.</>}</p><p>Whole-crop benchmark predictions below use separate models. Their confidence scores do not apply to this overlay. Hardware-obstruction review is pending.</p><p className="hash">Pixel model: {entry.checkpoint_sha256 || bundle.checkpoint_sha256}</p><Button size="small" href={entry.assets.download} download>Export pixel predictions</Button></details>
    </>}
    </section><SatelliteComparison photo={photo} target={target} evidence={satellite} range={range} /></div>
  </section>;
}
