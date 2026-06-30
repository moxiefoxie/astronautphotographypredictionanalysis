import { Avatar, Card, CardContent, Grid, Paper, Stack, Typography } from '@mui/material';
import SpaIcon from '@mui/icons-material/Spa';
import WaterIcon from '@mui/icons-material/Water';
import GrainIcon from '@mui/icons-material/Grain';
import OpacityIcon from '@mui/icons-material/Opacity';
import SectionTitle from '../shared/SectionTitle';
import Sparkline from '../shared/Sparkline';

export default function Predictions({ selected }) {
  const predictionCards = [
    ['Chlorophyll-a', selected.predicted.chlorophyll, 'mg/m³', `Confidence: ${selected.predicted.chlorophyllConfidence}%`, SpaIcon, '#e8f7ec'],
    ['Kd 490', selected.predicted.kd490, 'm⁻¹', `Confidence: ${selected.predicted.kdConfidence}%`, WaterIcon, '#eef5ff'],
    ['Water Clarity', selected.predicted.clarity, '', `Confidence: ${selected.predicted.clarityConfidence}%`, OpacityIcon, '#eefcff'],
  ];

  return (
    <Card>
      <CardContent>
        <SectionTitle title="Predicted Ocean / Coastal Conditions" />
        <Grid container spacing={1.5}>
          {predictionCards.map(([t, v, u, c, Icon, bg]) => (
            <Grid item xs={12} md={3} key={t}>
              <Paper sx={{ p: 2, border: '1px solid #e2e8f0' }}>
                <Stack direction="row" spacing={1} alignItems="center"><Avatar sx={{ bgcolor: bg, color: '#1769e0' }}><Icon /></Avatar><Typography variant="caption" fontWeight={900}>{t}</Typography></Stack>
                <Typography variant="h4" fontWeight={900} sx={{ mt: 2 }}>{v} <Typography component="span" variant="caption">{u}</Typography></Typography>
                <Typography variant="caption">{c}</Typography>
                <Sparkline />
              </Paper>
            </Grid>
          ))}
          <Grid item xs={12} md={3}>
            <Paper sx={{ p: 2, border: '1px solid #e2e8f0' }}>
              <Stack direction="row" spacing={1}><Avatar sx={{ bgcolor: '#f2eaff', color: '#7d4be8' }}><GrainIcon /></Avatar><Typography variant="caption" fontWeight={900}>Possible Indicators</Typography></Stack>
              {selected.indicators.map(([name, value, color]) => (
                <Stack key={name} direction="row" justifyContent="space-between" sx={{ mt: 1.3 }}><Typography variant="caption">{name}</Typography><Typography variant="caption" color={`${color}.main`} fontWeight={900}>{value}</Typography></Stack>
              ))}
            </Paper>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
}
