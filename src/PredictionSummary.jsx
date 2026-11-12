import React from 'react';
import { formatMeasurement as fmt } from './format';

export const targetNames = { chlor_a: 'Chlorophyll-a', kd_490: 'Kd(490)' };
export function satelliteReference(photo, target) {
  const match = photo.predictions[target]?.satellite;
  if (match?.targets?.[target]) return match.targets[target];
  return Object.values(photo.predictions).find(p => p.satellite?.targets?.[target])?.satellite.targets[target];
}

export default function PredictionSummary({ photo, target, onTarget, ranges, rangeLabel = 'Predicted map range' }) {
  return <div className="prediction-targets">{Object.entries(targetNames).map(([key, name]) => {
    const reference = satelliteReference(photo, key), prediction = photo.predictions[key];
    const units = prediction?.units || reference?.units || (key === 'chlor_a' ? 'mg/m³' : 'm⁻¹');
    return <button key={key} className={`prediction-target ${target === key ? 'active' : ''}`} aria-pressed={target === key} onClick={() => onTarget(key)}>
      <span className="target-name">{name}</span>
      <span className="target-comparison-values"><span><span className="value-label">{ranges ? rangeLabel : 'Whole-crop prediction'}</span><strong>{ranges ? ranges[key] ? `${fmt(ranges[key][0])}–${fmt(ranges[key][1])}` : 'Unavailable' : fmt(prediction?.value)}</strong><small>{units}</small></span>
        <span><span className="value-label">Satellite footprint mean</span><strong>{reference?.value != null ? fmt(reference.value) : 'Unavailable'}</strong><small>{reference?.value != null ? units : 'No satellite reference'}</small></span></span>
    </button>;
  })}</div>;
}
