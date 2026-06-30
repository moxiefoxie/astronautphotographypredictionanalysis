import { Box, Button, Card, CardContent, Divider, IconButton, Paper, Stack, Typography } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export default function ImageViewer({ selected }) {
  return (
    <Card>
      <CardContent>
        <Stack direction="row" justifyContent="space-between">
          <Typography fontWeight={900}>Selected Image: {selected.id}</Typography>
          <Button endIcon={<OpenInNewIcon />} size="small" href={selected.originalUrl} target="_blank">View Original</Button>
        </Stack>
        <Box sx={{ mt: 2, position: 'relative', borderRadius: 2, overflow: 'hidden', height: 385, bgcolor: '#0b1226' }}>
          <Box component="img" src={selected.img} sx={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          <Legend />
          <Overlay selected={selected} />
          <ZoomControls />
        </Box>
        <Stack direction="row" divider={<Divider orientation="vertical" flexItem />} sx={{ px: 2, py: 1.5, bgcolor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 1 }} spacing={2}>
          <Typography variant="body2">Region: {selected.region}</Typography>
          <Typography variant="body2">Lat: {selected.lat}</Typography>
          <Typography variant="body2">Lon: {selected.lon}</Typography>
          <Typography variant="body2">View Angle: {selected.viewAngle}</Typography>
          <InfoOutlinedIcon fontSize="small" />
        </Stack>
      </CardContent>
    </Card>
  );
}

function Legend() {
  const rows = [['Water', '#0bb7d8'], ['Coastline', '#69c943'], ['Possible Plume', '#7d4be8'], ['Sun Glint', '#e6b400'], ['Cloud / Haze', '#d4d9e2']];
  return <Paper sx={{ position: 'absolute', top: 16, left: 16, p: 1.2, bgcolor: 'rgba(7,18,42,.78)', color: 'white' }}>{rows.map(([l, c]) => <Stack key={l} direction="row" spacing={1} alignItems="center"><Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: c }} /><Typography variant="caption">{l}</Typography></Stack>)}</Paper>;
}

function Overlay({ selected }) {
  const overlays = {
    'ISS052-E-35339': `radial-gradient(ellipse at 28% 55%, rgba(105,201,67,.28) 0 18%, transparent 19%), radial-gradient(ellipse at 68% 43%, rgba(212,217,226,.38) 0 28%, transparent 29%), linear-gradient(118deg, transparent 38%, rgba(230,180,0,.22) 39%, transparent 40%)`,
    'ISS006-E-39830': `radial-gradient(ellipse at 47% 58%, rgba(11,183,216,.30) 0 24%, transparent 25%), radial-gradient(ellipse at 42% 56%, rgba(105,201,67,.32) 0 16%, transparent 17%), radial-gradient(ellipse at 65% 38%, rgba(212,217,226,.18) 0 14%, transparent 15%)`,
    'ISS005-E-21809': `radial-gradient(ellipse at 44% 48%, rgba(11,183,216,.25) 0 22%, transparent 23%), radial-gradient(ellipse at 39% 50%, rgba(105,201,67,.30) 0 16%, transparent 17%), radial-gradient(ellipse at 52% 58%, rgba(125,75,232,.22) 0 13%, transparent 14%)`,
  };
  return <Box sx={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: overlays[selected.id] ?? overlays['ISS052-E-35339'], mixBlendMode: 'screen' }} />;
}

function ZoomControls() {
  return <Stack sx={{ position: 'absolute', right: 16, bottom: 28, bgcolor: 'rgba(7,18,42,.7)', borderRadius: 1 }}><IconButton sx={{ color: 'white' }}><AddIcon /></IconButton><IconButton sx={{ color: 'white' }}><RemoveIcon /></IconButton><IconButton sx={{ color: 'white' }}><FullscreenIcon /></IconButton></Stack>;
}
