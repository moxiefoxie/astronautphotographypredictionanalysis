import { Stack, Typography } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export default function SectionTitle({ title }) {
  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
      <Typography fontWeight={900}>{title}</Typography>
      <InfoOutlinedIcon fontSize="small" color="disabled" />
    </Stack>
  );
}
