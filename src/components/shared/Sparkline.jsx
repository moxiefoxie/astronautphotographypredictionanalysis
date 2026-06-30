import { Box } from '@mui/material';

export default function Sparkline() {
  return <Box sx={{ mt: 1.5, height: 32, background: 'linear-gradient(135deg, transparent 0 10%, rgba(23,105,224,.20) 10% 20%, transparent 20% 30%, rgba(23,105,224,.20) 30% 45%, transparent 45%)', borderBottom: '2px solid #2da44e' }} />;
}
