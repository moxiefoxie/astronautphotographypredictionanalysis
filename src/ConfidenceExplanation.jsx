import React, { useState } from 'react';
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { formatMeasurement as fmt } from './format';

export default function ConfidenceExplanation({ photo, regional, pixel = false }) {
  const [open, setOpen] = useState(false);
  return <><Button size="small" onClick={() => setOpen(true)}>How to interpret confidence</Button>
    <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth><DialogTitle>Confidence and pixel accuracy</DialogTitle><DialogContent>
      <Typography component="p" sx={{ mb: 2 }}>A confidence percentage estimates how often an estimate will fall within ±25% of a quality-masked satellite reference. For example, 80% means about 8 of 10 comparable cases, not 80% certainty that every pixel is correct. The current photo’s satellite value is not needed to compute a supported score.</Typography>
      {pixel && <Typography component="p" sx={{ mb: 2 }}><strong>This pixel map has no calibrated pixel confidence.</strong> It reads red, green and blue image arrays and predicts a value at each rectified photo pixel. Training and evaluation use larger satellite regions. A fine output grid and a visually plausible pattern do not validate features smaller than the reference measurement.</Typography>}
      {regional && <Typography component="p" sx={{ mb: 2 }}>Regional scores apply only to the selected model and assessed water region. The regional model’s test evaluation covers {regional.evaluation?.photos} photos in {regional.evaluation?.groups} scene groups; {fmt(regional.evaluation?.scene_within25 * 100)}% of regional estimates agreed within ±25%, with equal weight per scene. This overall rate is different from an individual region’s score.</Typography>}
      {Object.entries(photo.predictions).map(([target, p]) => { const c = p.confidence; return <section key={target}><Typography fontWeight={700} sx={{ mt: 2 }}>{target === 'chlor_a' ? 'Chlorophyll-a' : 'Kd(490)'} · whole-crop model</Typography>
        {c?.status === 'available' ? <><Typography component="p" sx={{ mb: 2 }}>Displayed confidence: approximately {fmt(c.display_percent)}%. Scores are rounded to one significant figure; this does not establish certainty. Calibration used {c.calibration_groups} scene groups; validation used {c.validation?.groups} separate groups. In this reliability band, predicted agreement was {fmt(c.reliability_bin?.predicted * 100)}% and observed agreement was {fmt(c.reliability_bin?.observed * 100)}%.</Typography><Typography component="p" sx={{ mb: 2 }}>{c.limitations}</Typography><Typography variant="caption" className="hash">Calibration: {c.calibration_id}</Typography></> : <Typography component="p" sx={{ mb: 2 }}>{c?.reason || 'No supported calibrated confidence score is published for this output.'}</Typography>}
        {p.prediction_interval?.status === 'available' && <Typography component="p" sx={{ mb: 2 }}>A prediction interval is separate: its nominal {fmt(p.prediction_interval.nominal_coverage * 100)}% coverage describes performance across independent scenes, not the probability that this specific interval is correct.</Typography>}
      </section>; })}
      <Typography component="p" sx={{ mt: 2, mb: 2 }}>Whole-crop confidence does not transfer to regional or pixel maps. Satellite alignment is approximate, acquisitions can differ in time, and clouds, glint, land and camera processing can affect the comparison. Transparent areas mean excluded or missing data, never a measured zero.</Typography>
    </DialogContent><DialogActions><Button onClick={() => setOpen(false)}>Close</Button></DialogActions></Dialog>
  </>;
}
