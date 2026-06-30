import { Card, CardContent, Grid, Slider, Typography } from '@mui/material';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import FilterListIcon from '@mui/icons-material/FilterList';
import FilterCard from './FilterCard';
import FilterSelect from './FilterSelect';

export default function Filters({ filters, setFilters, images }) {
  const update = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));
  const regions = ['All Regions', ...new Set(images.map((img) => img.region))];

  return (
    <Grid container spacing={1.5}>
      <FilterCard label="Date Range" value="2002-01-01 – 2024-12-31" icon={<CalendarMonthIcon />} />
      <FilterSelect label="Region" value={filters.region} options={regions} onChange={(value) => update('region', value)} />
      <FilterSelect label="Ocean / Coastal Type" value={filters.coastalType} options={['All', 'Coastal / Shelf Water', 'Reef / Lagoon', 'Island / Gulf']} onChange={(value) => update('coastalType', value)} />
      <FilterSelect label="Satellite Match" value={filters.satelliteMatch} options={['All', 'Good', 'Fair']} onChange={(value) => update('satelliteMatch', value)} />
      <FilterSelect label="Prediction Available" value={filters.predictionAvailable} options={['All', 'Yes', 'No']} onChange={(value) => update('predictionAvailable', value)} />
      <Grid item xs={12} md={2}>
        <Card><CardContent sx={{ py: 1.4 }}><Typography variant="caption" color="text.secondary">Min. Confidence</Typography><Slider value={filters.minConfidence} onChange={(_, value) => update('minConfidence', value)} size="small" min={0} max={100} /></CardContent></Card>
      </Grid>
      <Grid item xs={12} md={1.1}>
        <Card><CardContent sx={{ py: 1.4, textAlign: 'center' }}><FilterListIcon fontSize="small" /><Typography variant="body2" color="primary" fontWeight={700}>Filters</Typography></CardContent></Card>
      </Grid>
    </Grid>
  );
}
