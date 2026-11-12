import React from 'react';
import { formatMeasurement as fmt } from './format';

const names = { chlor_a: 'Chlorophyll-a', kd_490: 'Kd(490)' };
export default function SatelliteAgreement({ agreement }) {
  return <div className="satellite-agreement">
    <strong>Matched-region error</strong>
    <div className="agreement-values">{Object.entries(names).map(([target, name]) => {
      const value = agreement?.targets?.[target];
      return <span key={target}>{name}: <strong>{value ? `${fmt(value.mean_absolute_percentage_error)}%` : 'Unavailable'}</strong>{value && ` · ${value.region_count} regions`}</span>;
    })}</div>
    <details><summary>How this error is calculated</summary><p>For each assessed region, error = |prediction − satellite| ÷ satellite × 100. The filter uses the average of these absolute errors, with equal weight per region and at least four valid comparisons per target. It uses full-precision values, so a rounded display may appear equal to the limit even when it does not pass.</p><p>These are pooled predictions from the pixel model and satellite measurements for the same regions, before the pixel display mask. They differ from the whole-footprint satellite mean and the separate whole-crop model. Registration is approximate; this is satellite agreement, not calibrated confidence or proof of individual-pixel accuracy.</p>
      <table className="comparison-table"><caption>Geometric means across the compared regions</caption><thead><tr><th>Target</th><th>Pixel model</th><th>Satellite</th></tr></thead><tbody>{Object.entries(names).map(([target,name]) => { const value = agreement?.targets?.[target]; return <tr key={target}><td>{name}<small>{target === 'chlor_a' ? 'mg/m³' : 'm⁻¹'}</small></td><td>{fmt(value?.prediction_geometric_mean)}</td><td>{fmt(value?.satellite_geometric_mean)}</td></tr>; })}</tbody></table>
    </details>
  </div>;
}
