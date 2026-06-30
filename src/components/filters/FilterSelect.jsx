import { Card, CardContent, Grid, MenuItem, Select, Typography } from '@mui/material';

export default function FilterSelect({ label, value, options, onChange }) {
  return (
    <Grid item xs={12} md={1.8}>
      <Card>
        <CardContent sx={{ py: 1.2 }}>
          <Typography variant="caption" color="text.secondary">{label}</Typography>
          <Select fullWidth variant="standard" value={value} disableUnderline onChange={(event) => onChange(event.target.value)}>
            {options.map((option) => <MenuItem value={option} key={option}>{option}</MenuItem>)}
          </Select>
        </CardContent>
      </Card>
    </Grid>
  );
}
