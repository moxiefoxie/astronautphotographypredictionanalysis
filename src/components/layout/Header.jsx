import { Box, Button, Typography } from '@mui/material';
import HelpIcon from '@mui/icons-material/Help';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

export default function Header() {
  return (
    <Box sx={{ height: 82, px: 3, display: 'flex', alignItems: 'center', borderBottom: '1px solid #e2e8f0', bgcolor: 'white' }}>
      <Box>
        <Typography variant="h5" fontWeight={900}>Astronaut Photography Prediction & Analysis</Typography>
        <Typography color="text.secondary">Explore. Analyze. Compare.</Typography>
      </Box>
      <Box sx={{ flex: 1 }} />
      <Button startIcon={<HelpIcon />} variant="outlined" sx={{ mr: 1.5 }}>Help</Button>
      <Button startIcon={<CloudUploadIcon />} variant="contained">Upload Image</Button>
    </Box>
  );
}
