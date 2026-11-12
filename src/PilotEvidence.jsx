import React, { useEffect, useState } from 'react';
import { Alert, Button, Chip, Slider, Stack, Typography } from '@mui/material';
import { imageSource, samplePreview } from './photoImages';
import { downloadJSON } from './api';
import pilot from './evidence-pilot.json';
import confidenceStatus from './confidence-status.json';

export const pilotIds = new Set(Object.keys(pilot));
export const referencePilotIds = new Set(Object.entries(pilot).filter(([,entry]) => entry.has_reference !== false).map(([id]) => id));
const names = { chlor_a: 'Chlorophyll-a', kd_490: 'Kd(490)' };
const number = v => Number(v).toLocaleString(undefined, { maximumSignificantDigits: 1 });
const direction = (base, next) => `${next < base ? 'decreases' : 'increases'} by ${number(Math.abs(next / base - 1) * 100)}%`;
const regionName = i => `${['top', 'upper-middle', 'lower-middle', 'bottom'][Math.floor(i / 4)]} row, column ${i % 4 + 1}`;
// Continuous purple-to-yellow scale, shared with the visible legend.
const stops = [[68,1,84], [59,82,139], [33,145,140], [94,201,98], [253,231,37]];
function referenceColor(value, range) {
  const t = Math.max(0, Math.min(1, (value - Math.log10(range[0])) / Math.log10(range[1] / range[0]))) * 4;
  const i = Math.min(3, Math.floor(t)), f = t - i;
  return `rgb(${stops[i].map((v, c) => Math.round(v + f * (stops[i + 1][c] - v))).join(',')})`;
}

export default function PilotEvidence({ photo, showPilot }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [target, setTarget] = useState('chlor_a'), [mode, setMode] = useState('photo');
  const [opacity, setOpacity] = useState(55), [selected, setSelected] = useState(null);
  const [ready, setReady] = useState(false), [failed, setFailed] = useState(false), [attempt, setAttempt] = useState(0);
  const preview = samplePreview(photo);
  const choices = pilot[photo.id] ? [pilot[photo.id], ...(pilot[photo.id].variants || [])] : [];
  const entry = choices.find(candidate => candidate.asset_id === photo.preview?.asset_id && Object.entries(candidate.model_ids).every(([t, id]) => id === photo.predictions[t]?.model.id));
  useEffect(() => {
    setData(null); setError('');
    if (!entry) return;
    const ctrl = new AbortController();
    fetch(entry.url, { signal: ctrl.signal }).then(async r => {
      if (!r.ok) throw new Error('The evidence file could not be loaded.');
      const evidence = await r.json();
      const valid = evidence.photo_id === photo.id && evidence.input_asset_id === photo.preview?.asset_id && preview &&
        evidence.source_sha256 === preview.source_sha256 && Object.entries(evidence.sensitivity).every(([t, s]) => s.model_id === photo.predictions[t]?.model.id);
      if (!valid) throw new Error('This evidence belongs to a different model or input crop.');
      setData(evidence);
      setMode('photo');
    }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => ctrl.abort();
  }, [photo.id, entry?.url]);
  const prediction = photo.predictions[target];
  const confidence = prediction?.confidence;
  const assessment = confidenceStatus[target]?.applies_to_model_ids.includes(prediction?.model.id) ? confidenceStatus[target] : null;
  const scored = confidence?.status === 'available';
  const interval = prediction?.prediction_interval;
  const calibrated = interval?.status === 'available';
  const benchmarkError = prediction?.model.test_metrics?.median_error_factor;
  const sensitivity = data?.sensitivity[target], reference = data?.reference?.layers[target];
  const tile = selected ?? sensitivity?.strongest_tile ?? 0;
  const maxEffect = sensitivity ? Math.max(.000001, ...sensitivity.delta_log10.map(Math.abs)) : 1;
  const bounds = sensitivity?.input_bounds;
  const src = imageSource(photo);
  const changeTarget = t => { setTarget(t); setSelected(null); };
  return <div className="pilot-evidence">
    <Typography component="h3" variant="body2" fontWeight={700} sx={{ mb: 1 }}>Whole-crop model predictions</Typography>
    <div className="prediction-targets" aria-label="Predictions and confidence for both targets">
      {Object.entries(names).map(([t, name]) => {
        const p = photo.predictions[t], c = p?.confidence;
        return <button key={t} className={`prediction-target ${target === t ? 'active' : ''}`} aria-pressed={target === t} onClick={() => changeTarget(t)}>
          <span>{name}</span><strong>{p ? number(p.value) : '—'} <small>{p?.units}</small></strong>
          <span className={c?.status === 'available' ? 'confidence-available' : ''}>{!p ? 'No prediction' : c?.status === 'available' ? `${number(c.display_percent)}% confidence` : 'Confidence not validated'}</span>
        </button>;
      })}
    </div>
    <section className="prediction-confidence" aria-label="Prediction confidence">
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
        <Typography component="h3" variant="body2" fontWeight={700}>Prediction confidence · {names[target]}</Typography>
        <Chip size="small" variant="outlined" label={!prediction ? 'No prediction' : scored ? 'Calibrated confidence' : calibrated ? 'Calibrated interval' : confidence || assessment ? 'Confidence not validated' : 'Not calibrated'} />
      </Stack>
      {scored ? <><Typography component="p" className="confidence-value">{number(confidence.display_percent)}% confidence</Typography><Typography variant="body2" color="text.secondary">Estimated chance this {names[target]} prediction is within ±25% of the satellite reference level. A satellite match for this photo is not required.</Typography>{!prediction.satellite && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: .5 }}>Learned from other photos with satellite measurements; this photo has no measurement to check against.</Typography>}</> : calibrated ? <Typography variant="body2" sx={{ mt: 1 }}><strong>{number(interval.lower)}–{number(interval.upper)} {prediction.units}</strong> · {number(interval.nominal_coverage * 100)}% prediction interval. Coverage describes independent scenes, not the probability that this photo is correct.</Typography> : <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{prediction ? confidence?.reason || assessment?.message || 'A reliable confidence percentage is not available for this prediction. Independent calibration scenes are needed.' : 'No model prediction is recorded for this target.'}</Typography>}
      {benchmarkError != null && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: .75 }}>Model benchmark: {number(benchmarkError)}× median error factor on the held-out test set. This measures overall model performance, not confidence for this photo.</Typography>}
      {scored && <details><summary>How this confidence was checked</summary><p>Calibrated using {confidence.calibration_groups} scene groups. Evaluated on {confidence.validation.groups} separate test scene groups.</p><p>For this confidence band, the mean predicted confidence was {number(confidence.reliability_bin.predicted * 100)}%; the observed rate within ±25% was {number(confidence.reliability_bin.observed * 100)}%, with equal weight per scene.</p><p>{confidence.limitations}</p><p>Saved scores use 5-percentage-point bands; the dashboard displays one significant figure. Exports preserve saved precision. Satellite comparisons evaluate research estimates; these are not field measurements.</p><p className="hash">{confidence.calibration_id}</p></details>}
      {assessment && !scored && <details><summary>Confidence validation details</summary><p>A new candidate used {assessment.calibration_groups} calibration scene groups and {assessment.evaluation_groups} separate evaluation groups. It did not pass the preset reliability checks, so its scores were not published.</p><p>For example, its {number(assessment.example_band.predicted * 100)}% confidence band achieved {number(assessment.example_band.observed * 100)}% agreement within ±25%, across {assessment.example_band.groups} evaluation groups. These results describe the rejected candidate, not the existing prediction shown above.</p><p className="hash">{assessment.calibration_id}</p></details>}
      {calibrated && <details><summary>Confidence calibration evidence</summary><p>{interval.group_count} independent scene groups · {interval.validation_status}</p><p>{interval.limitation}</p><p className="hash">{interval.calibration_id}</p></details>}
    </section>
    <Alert severity="info" sx={{ mt: 1.5 }}><strong>Local prediction map not available yet.</strong> These models estimate one value for the whole crop. They have not been validated to locate higher or lower chlorophyll or Kd(490) within it. Whole-crop confidence does not apply to individual regions.</Alert>
    {entry && <Stack direction="row" sx={{ flexWrap: 'wrap', gap: .75, my: 1.5 }}>
      {[['photo', 'Photo'], ['sensitivity', 'What influences the estimate'], ['reference', 'Satellite measurements']].map(([value, name]) => <Button size="small" key={value} disabled={(!data && value !== 'photo') || (value === 'reference' && !reference)} variant={mode === value ? 'contained' : 'outlined'} onClick={() => { setMode(value); setSelected(null); }}>{name}</Button>)}
    </Stack>}
    {data && mode === 'reference' && <Typography variant="body2" fontWeight={700} sx={{ mb: 1 }}>Satellite measurements · not model predictions</Typography>}
    {data && mode === 'sensitivity' && <Typography variant="body2" fontWeight={700} sx={{ mb: 1 }}>Sensitivity experiment · not a concentration map</Typography>}
    {error && <Alert severity="error">{error}</Alert>}
    <div className="evidence-stage" style={{ maxWidth: preview ? `${340 * preview.width / preview.height}px` : 480, aspectRatio: preview ? `${preview.width}/${preview.height}` : '1', margin: 0 }}>
      <img src={attempt ? `${src}?retry=${attempt}` : src} alt={`Astronaut photograph ${photo.id}`} onLoad={() => { setReady(true); setFailed(false); }} onError={() => { setReady(false); setFailed(true); }} />
      {!ready && <div className="image-status" role="status">{failed ? <>Photo unavailable <Button onClick={() => { setFailed(false); setAttempt(n => n + 1); }}>Retry photo</Button></> : 'Loading photograph…'}</div>}
      {ready && data && mode !== 'photo' && <svg className="evidence-layer" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label={mode === 'sensitivity' ? 'Model occlusion sensitivity regions' : 'Approximate satellite reference overlay'}>
        {mode === 'reference' && reference && reference.grid_log10.flatMap((line, y) => line.map((value, x) => value == null ? null : <rect key={`${x}-${y}`} x={x * 1000 / line.length} y={y * 1000 / reference.grid_log10.length} width={1000 / line.length} height={1000 / reference.grid_log10.length} fill={referenceColor(value, reference.range)} fillOpacity={opacity / 100}><title>{number(10 ** value)} {reference.units} · satellite pixel</title></rect>))}
        {mode === 'sensitivity' && sensitivity.tile_boxes.map(([x0, y0, x1, y1], i) => <rect key={i} role="button" tabIndex={0}
          aria-label={`${regionName(i)}: obscuring this region ${direction(sensitivity.replayed_value, sensitivity.occluded_values[i])}`}
          x={x0 * 1000} y={y0 * 1000} width={(x1 - x0) * 1000} height={(y1 - y0) * 1000}
          fill={sensitivity.delta_log10[i] >= 0 ? '#ef8a23' : '#32b5ef'} fillOpacity={Math.abs(sensitivity.delta_log10[i]) / maxEffect * opacity / 100}
          stroke={tile === i ? 'white' : 'rgba(255,255,255,.25)'} strokeWidth={tile === i ? 5 : 1} vectorEffect="non-scaling-stroke"
          onClick={() => setSelected(i)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(i); } }}><title>{regionName(i)}</title></rect>)}
        {mode === 'sensitivity' && bounds && <rect x={bounds[0] * 1000} y={bounds[1] * 1000} width={(bounds[2] - bounds[0]) * 1000} height={(bounds[3] - bounds[1]) * 1000} fill="none" stroke="white" strokeWidth="2" strokeDasharray="7 4" vectorEffect="non-scaling-stroke" pointerEvents="none" />}
      </svg>}
    </div>
    {entry && !data && !error && <Typography variant="body2" sx={{ mt: 1 }}>Loading verified model evidence…</Typography>}
    {data && !reference && <Typography variant="body2" sx={{ mt: 1 }}>No satellite measurement is available for this photo. Model estimates and any supported confidence score still work.</Typography>}
    {data && mode !== 'photo' && <Stack direction="row" sx={{ alignItems: 'center', gap: 2, mt: 1 }}><Typography variant="caption">Layer opacity</Typography><Slider size="small" aria-label="Evidence opacity" value={opacity} onChange={(_, v) => setOpacity(v)} sx={{ flex: 1 }} /><Typography variant="caption">{opacity}%</Typography></Stack>}
    {data && mode === 'sensitivity' && <>
      <div className="sensitivity-key"><span><i style={{ background: '#ef8a23' }} />Hiding region lowers prediction</span><span><i style={{ background: '#32b5ef' }} />Hiding region raises prediction</span></div>
      <div className="evidence-reading" aria-live="polite"><strong>{selected == null ? 'Largest tested change' : 'Selected region'} · {regionName(tile)}</strong><p>Replacing this region with the image’s mean color {direction(sensitivity.replayed_value, sensitivity.occluded_values[tile])}: <b>{number(sensitivity.replayed_value)} → {number(sensitivity.occluded_values[tile])} {prediction.units}</b>. Location, time, sun and cloud inputs were held fixed.</p></div>
      <Typography variant="body2" color="text.secondary">Click a square to inspect it. Colors show how the saved model responds to obscuring a region. Intensity is relative within this photo and target; it does not measure local chlorophyll levels or Kd(490) values. The dashed boundary is the center crop the model actually sees.</Typography>
    </>}
    {data && reference && mode === 'reference' && <>
      <div className="legend-scale" /><div className="legend-labels"><span>{reference.range[0]}</span><span>{names[target]} · {reference.units} · log scale</span><span>{reference.range[1]}</span></div>
      <div className="evidence-reading"><strong>Satellite evidence · {number(Math.abs(data.reference.delta_minutes))} minutes from the photograph</strong><p>{number(reference.display_coverage * 100)}% of display cells have a nearby quality-passing satellite pixel. Transparent cells have no usable reference.</p></div>
      <Alert severity="warning" sx={{ mt: 1 }}>Approximate projection from the recorded corners. Satellite land/cloud/glint flags are applied; photo-specific masks and independent alignment checks are still needed. This layer is supporting evidence, not the model’s explanation.</Alert>
    </>}
    {!entry && <Alert severity="info" sx={{ mt: 2 }} action={<Button onClick={showPilot}>Open pilot</Button>}>This photo has saved whole-crop predictions. Sensitivity experiments are available for {pilotIds.size} pilot photos.</Alert>}
    <details className="satellite-comparison"><summary>Compare with satellite measurements (optional)</summary>
      <Typography variant="body2" sx={{ my: 1 }}>This checks agreement with a separate measurement. The percentage difference is not prediction confidence.</Typography>
      <div className="evidence-metrics">
        <div><span>Model prediction</span><strong>{prediction ? number(prediction.value) : '—'} <small>{prediction?.units}</small></strong></div>
        <div><span>Satellite measurement</span><strong>{prediction?.satellite ? number(prediction.satellite.targets[target].value) : 'Unavailable'} <small>{prediction?.satellite && prediction.units}</small></strong></div>
        <div><span>Difference from measurement</span><strong>{prediction?.satellite ? `${prediction.difference >= 0 ? '+' : '−'}${number(Math.abs(prediction.difference) / prediction.satellite.targets[target].value * 100)}%` : '—'}</strong></div>
      </div>
    </details>
    {data && <details><summary>Method, limitations & evidence export</summary><p>{sensitivity.method}</p><p>{sensitivity.limitations}</p>{data.reference && <p>{data.reference.method} {data.reference.registration} {data.reference.mask_status}</p>}<p>Replay matched the saved prediction within {sensitivity.replay_abs_log10_error.toExponential(2)} log10 units. {data.reference ? 'Reference aggregates were reproduced from the source satellite pixels.' : 'No satellite values were used for this explanation.'}</p><p className="hash">Model: {sensitivity.model_id}</p>{data.reference && <p className="hash">Granule: {data.reference.granule_id}</p>}<p className="hash">Input SHA-256: {data.source_sha256}</p><Button size="small" onClick={() => downloadJSON(data, `${photo.id}-evidence.json`)}>Export evidence JSON</Button></details>}
  </div>;
}
