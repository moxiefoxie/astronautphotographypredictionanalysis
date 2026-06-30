import { Box, Card, CardContent, LinearProgress, Stack, Typography } from '@mui/material';
import Donut from '../shared/Donut';
import SectionTitle from '../shared/SectionTitle';

export default function UsefulnessCard({ selected }) {
  const vals = [
    ['Metadata Quality', selected.scores.metadata],
    ['Visual Clarity', selected.scores.visualClarity],
    ['Ocean Coverage', selected.scores.oceanCoverage],
    ['Satellite Match Quality', selected.scores.satelliteMatch],
    ['Geolocation Confidence', selected.scores.geolocation],
  ];

  return (
    <Card>
      <CardContent>
        <SectionTitle title="Image Usefulness Score" />
        <Stack direction="row" spacing={3} alignItems="center">
          <Donut value={selected.usefulness} color="#7750d9" label="/100" suffix="" />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            {vals.map(([label, value]) => (
              <Box key={label} sx={{ mb: 1.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="body2" noWrap sx={{ pr: 1 }}>{label}</Typography><Typography variant="body2" fontWeight={900}>{value}</Typography></Stack>
                <LinearProgress variant="determinate" value={value} sx={{ height: 6, borderRadius: 2, mt: 0.5 }} />
              </Box>
            ))}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}
