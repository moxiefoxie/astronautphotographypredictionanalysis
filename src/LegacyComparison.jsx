import React, { useState } from 'react';
import { Typography } from '@mui/material';
import PhotoMetadata from './PhotoMetadataTable.jsx';
import PredictionSummary from './PredictionSummary';
import OverlayViewer from './OverlayViewer';
import SatelliteComparison, { useSatelliteMatrix } from './SatelliteComparison';

export default function LegacyComparison({ photo, writesEnabled }) {
  const [target,setTarget] = useState('chlor_a');
  const satellite = useSatelliteMatrix(photo);
  return <section>
    <PredictionSummary photo={photo} target={target} onTarget={setTarget} />
    <Typography variant="body2" color="text.secondary" sx={{my:1.5}}>Whole-crop predictions and satellite footprint means. Spatial layers retain their own model provenance and scale.</Typography>
    <div className="comparison-row"><PhotoMetadata photo={photo} /><section className="comparison-panel"><div className="comparison-panel-heading"><Typography component="h4" fontWeight={800}>Photograph & model evidence</Typography></div><OverlayViewer photo={photo} writesEnabled={writesEnabled} /></section><SatelliteComparison photo={photo} target={target} evidence={satellite} /></div>
  </section>;
}
