import React from 'react';
import { Box, CssBaseline, Stack, ThemeProvider } from '@mui/material';
import { theme } from './theme/theme';
import { images } from './data/mockImages';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import Filters from './components/filters/Filters';
import SearchResults from './components/dashboard/SearchResults';
import ImageViewer from './components/dashboard/ImageViewer';
import Predictions from './components/dashboard/Predictions';
import SatelliteMatch from './components/dashboard/SatelliteMatch';
import ConfidenceCard from './components/dashboard/ConfidenceCard';
import UsefulnessCard from './components/dashboard/UsefulnessCard';
import DataSummary from './components/dashboard/DataSummary';
import QuickActions from './components/dashboard/QuickActions';
import LocationOverview from './components/dashboard/LocationOverview';

export default function App() {
  const [selected, setSelected] = React.useState(images[0]);
  const [filters, setFilters] = React.useState({
    region: 'All Regions',
    coastalType: 'All',
    satelliteMatch: 'All',
    predictionAvailable: 'All',
    minConfidence: 0,
  });

  const filteredImages = React.useMemo(() => {
    return images.filter((img) => (
      (filters.region === 'All Regions' || img.region === filters.region) &&
      (filters.coastalType === 'All' || img.coastalType === filters.coastalType) &&
      (filters.satelliteMatch === 'All' || img.satellite.matchQuality === filters.satelliteMatch) &&
      (filters.predictionAvailable === 'All' || img.predictionAvailable === (filters.predictionAvailable === 'Yes')) &&
      img.confidence >= filters.minConfidence
    ));
  }, [filters]);

  React.useEffect(() => {
    if (!filteredImages.some((img) => img.id === selected.id)) {
      setSelected(filteredImages[0] ?? images[0]);
    }
  }, [filteredImages, selected.id]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
        <Sidebar />
        <Box component="main" sx={{ flex: 1, minWidth: 0 }}>
          <Header />
          <Box sx={{ p: 3 }}>
            <Filters filters={filters} setFilters={setFilters} images={images} />
            <Box sx={{ mt: 2, display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '320px minmax(520px, 1fr) 420px' }, gap: 2.5, alignItems: 'start' }}>
              <SearchResults imagesToShow={filteredImages} selected={selected} onSelect={setSelected} />
              <Stack spacing={2.5}>
                <ImageViewer selected={selected} />
                <Predictions selected={selected} />
                <SatelliteMatch selected={selected} />
              </Stack>
              <Stack spacing={2.5}>
                <ConfidenceCard selected={selected} />
                <UsefulnessCard selected={selected} />
                <DataSummary selected={selected} />
                <QuickActions selected={selected} />
                <LocationOverview selected={selected} />
              </Stack>
            </Box>
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
