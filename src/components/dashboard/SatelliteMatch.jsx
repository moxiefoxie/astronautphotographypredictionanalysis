import { Card, CardContent, Chip, Grid, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SectionTitle from '../shared/SectionTitle';

export default function SatelliteMatch({ selected }) {
  return (
    <Card>
      <CardContent>
        <SectionTitle title="Satellite Match" />
        <Grid container spacing={2}>
          <Grid item xs={4}><Typography variant="caption">Product</Typography><Typography fontWeight={900} variant="body2">{selected.satellite.product}</Typography></Grid>
          <Grid item xs={2}><Typography variant="caption">Date</Typography><Typography fontWeight={900} variant="body2">{selected.satellite.date}</Typography></Grid>
          <Grid item xs={3}><Typography variant="caption">Satellite Reference</Typography><Typography variant="body2">Chl-a {selected.satellite.chlorophyll} · Kd 490 {selected.satellite.kd490}</Typography></Grid>
          <Grid item xs={3}><Typography variant="caption">Difference</Typography><Typography variant="body2">Chl-a {selected.satellite.chlorophyllDiff} · Kd {selected.satellite.kdDiff}</Typography></Grid>
        </Grid>
        <Chip sx={{ mt: 2 }} color="success" icon={<CheckCircleIcon />} label={`Match Quality: ${selected.satellite.matchQuality}`} />
      </CardContent>
    </Card>
  );
}
