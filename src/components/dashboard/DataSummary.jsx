import { Card, CardContent, Grid, Typography } from '@mui/material';
import SectionTitle from '../shared/SectionTitle';

export default function DataSummary({ selected }) {
  const rows = [
    ['Photo Date', selected.date], ['Camera', selected.camera], ['Mission', selected.mission], ['Orbit', selected.altitude],
    ['Image ID', selected.id], ['Resolution', selected.resolution], ['Lighting', `Sun elev. ${selected.sunElevation}`], ['Cloud Cover', selected.cloudCover],
  ];
  return (
    <Card>
      <CardContent>
        <SectionTitle title="Data Summary" />
        <Grid container spacing={2}>{rows.map(([label, value]) => <Grid item xs={6} md={3} key={label}><Typography variant="caption" color="text.secondary">{label}</Typography><Typography variant="body2" fontWeight={900}>{value}</Typography></Grid>)}</Grid>
      </CardContent>
    </Card>
  );
}
