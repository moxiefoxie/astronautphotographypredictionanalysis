import { Card, CardContent, Grid, Stack, Typography, Box } from '@mui/material';

export default function FilterCard({ label, value, icon }) {
  return (
    <Grid item xs={12} md={2}>
      <Card>
        <CardContent sx={{ py: 1.4 }}>
          <Stack direction="row" justifyContent="space-between">
            <Box>
              <Typography variant="caption" color="text.secondary">{label}</Typography>
              <Typography fontWeight={700}>{value}</Typography>
            </Box>
            {icon}
          </Stack>
        </CardContent>
      </Card>
    </Grid>
  );
}
