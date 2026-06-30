import { Box, Typography } from '@mui/material';

export default function Donut({ value, color, label, suffix = '%' }) {
  return (
    <Box sx={{ width: 132, height: 132, borderRadius: '50%', background: `conic-gradient(${color} ${value * 3.6}deg, #e5eaf2 0)`, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
      <Box sx={{ width: 96, height: 96, borderRadius: '50%', bgcolor: 'white', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
          <Typography sx={{ fontSize: 54, fontWeight: 900, lineHeight: 0.9 }}>{value}</Typography>
          {suffix && <Typography sx={{ fontSize: 22, fontWeight: 800, lineHeight: 1, mt: 0.6 }}>{suffix}</Typography>}
        </Box>
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: label === '/100' ? 'text.secondary' : 'success.main', fontWeight: 800, lineHeight: 1 }}>{label}</Typography>
      </Box>
    </Box>
  );
}
