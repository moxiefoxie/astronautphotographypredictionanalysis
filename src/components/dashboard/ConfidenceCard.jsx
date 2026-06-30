import { Box, Card, CardContent, Stack, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import Donut from '../shared/Donut';
import SectionTitle from '../shared/SectionTitle';

export default function ConfidenceCard({ selected }) {
  return (
    <Card>
      <CardContent>
        <SectionTitle title="Prediction Confidence" />
        <Stack direction="row" alignItems="center" spacing={4}>
          <Donut value={selected.confidence} color="#39a64a" label={selected.label.replace(' Confidence', '')} />
          <Box>
            {selected.confidenceFactors.map(([text, ok]) => (
              <Stack key={text} direction="row" spacing={1} sx={{ mb: 1 }}>
                {ok ? <CheckCircleIcon color="success" fontSize="small" /> : <WarningAmberIcon color="warning" fontSize="small" />}
                <Typography variant="body2">{text}</Typography>
              </Stack>
            ))}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}
