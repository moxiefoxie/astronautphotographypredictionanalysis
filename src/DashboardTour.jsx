import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';

const storageKey = 'appa-dashboard-tour-v1';
const steps = [
  ['error', 'Choose an acceptable error', 'Enter a maximum error, such as 25%, and choose chlorophyll-a, Kd(490), or both. We average absolute percentage differences from satellite measurements over matching regions. Both means each target must pass. Leave the limit blank to see all results.'],
  ['results', 'Select a photograph', 'Choose a thumbnail to open its analysis. Previous and Next let you browse the rest of the matching photographs.'],
  ['predictions', 'Read the numbers', 'Choose chlorophyll-a or Kd(490) to switch both overlays. The pixel range and satellite footprint mean summarize different areas. The matched-region error below them is the comparison used by the filter; expand its explanation to see the calculation and regional means.'],
  ['overlays', 'Compare the overlays', 'The predicted and satellite overlays appear beside the metadata table. Inspect a pixel or satellite cell, change opacity, or show the photo alone. Shared color scales help comparison, but matching colors do not establish pixel accuracy.'],
  ['export', 'Keep your findings', 'Export every matching result, or save the entire search to your collection. Individual-photo actions are below its analysis. Collections stay in this browser, and exports include NASA photo links. You can reopen this walkthrough with Take a tour.'],
];

export default function DashboardTour({ ready, open, setOpen }) {
  const [step, setStep] = useState(0);
  const checked = useRef(false);
  useEffect(() => {
    if (!ready || checked.current) return;
    checked.current = true;
    try { if (localStorage.getItem(storageKey)) return; } catch { /* Session-only tour. */ }
    setOpen(true);
  }, [ready, setOpen]);
  useLayoutEffect(() => {
    const clearHighlight = () => document.querySelectorAll('.tour-highlight').forEach(element => element.classList.remove('tour-highlight'));
    clearHighlight();
    if (!open) return;
    const target = document.querySelector(`[data-tour="${steps[step][0]}"]`);
    if (!target) return;
    target.classList.add('tour-highlight');
    target.scrollIntoView({ block: 'start', behavior: 'instant' });
    return clearHighlight;
  }, [open, step]);
  function finish() {
    try { localStorage.setItem(storageKey, 'seen'); } catch { /* Still closes for this session. */ }
    setOpen(false);
  }
  return <Dialog open={open} onClose={finish} aria-labelledby="tour-title" aria-describedby="tour-description" className="dashboard-tour" maxWidth="xs" fullWidth slotProps={{ transition: { onExited: () => setStep(0) }, backdrop: { sx: { backgroundColor: 'rgba(18,35,59,.16)' } } }}>
    <DialogTitle id="tour-title"><Typography component="span" variant="overline" sx={{ display: 'block' }}>Quick tour · {step + 1} of {steps.length}</Typography>{steps[step][1]}</DialogTitle>
    <DialogContent><Typography id="tour-description">{steps[step][2]}</Typography></DialogContent>
    <DialogActions><Button onClick={finish}>Skip tour</Button><div style={{ flex: 1 }} /><Button disabled={step === 0} onClick={() => setStep(s => s - 1)}>Back</Button><Button autoFocus variant="contained" onClick={() => step === steps.length - 1 ? finish() : setStep(s => s + 1)}>{step === steps.length - 1 ? 'Finish' : 'Next'}</Button></DialogActions>
  </Dialog>;
}
