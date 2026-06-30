import { Box, Button, Card, CardContent, Typography } from '@mui/material';
import PlaceIcon from '@mui/icons-material/Place';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

export default function LocationOverview({ selected }) {
  return (
    <Card>
      <CardContent>
        <Typography fontWeight={900} sx={{ mb: 1.5 }}>Location Overview</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Box sx={{ flex: 1, height: 135, borderRadius: 2, background: 'linear-gradient(135deg,#254f66,#062b57 55%,#1590a9)', position: 'relative' }}><PlaceIcon sx={{ position: 'absolute', left: '58%', top: '40%', color: '#a46bf5', fontSize: 42 }} /></Box>
          <Box>
            <Typography fontWeight={900}>{selected.region}</Typography>
            <Typography variant="body2" color="text.secondary">{selected.lat}, {selected.lon}</Typography>
            <Button sx={{ mt: 3 }} variant="outlined" size="small" href={selected.originalUrl} target="_blank" endIcon={<OpenInNewIcon />}>Open NASA Page</Button>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
