import { Avatar, Box, Stack, Typography } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import MapIcon from '@mui/icons-material/Map';
import CollectionsBookmarkIcon from '@mui/icons-material/CollectionsBookmark';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import SettingsIcon from '@mui/icons-material/Settings';
import WaterIcon from '@mui/icons-material/Water';

export default function Sidebar() {
  const items = [
    [DashboardIcon, 'Dashboard', true], [SearchIcon, 'Search'], [MapIcon, 'Map'],
    [CollectionsBookmarkIcon, 'Collections'], [AnalyticsIcon, 'Analytics'],
    [CompareArrowsIcon, 'Compare'], [MenuBookIcon, 'Data Dictionary'], [SettingsIcon, 'Settings'],
  ];

  return (
    <Box sx={{ width: 184, bgcolor: '#06142d', color: 'white', p: 2, display: { xs: 'none', md: 'flex' }, flexDirection: 'column' }}>
      <Stack direction="row" alignItems="center" spacing={1.2} sx={{ mb: 4, px: 1 }}>
        <WaterIcon sx={{ color: '#1da9ff', fontSize: 34 }} />
      </Stack>
      <Stack spacing={1}>
        {items.map(([Icon, label, active]) => (
          <Box key={label} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 1.4, py: 1.2, borderRadius: 1.5, bgcolor: active ? '#174ea6' : 'transparent' }}>
            <Icon fontSize="small" />
            <Typography variant="body2" fontWeight={700}>{label}</Typography>
          </Box>
        ))}
      </Stack>
      <Box sx={{ flex: 1 }} />
      <Typography variant="caption" sx={{ color: '#92a0bd', mb: 2 }}>Dark mode &nbsp; ●</Typography>
      <Stack direction="row" spacing={1.2} alignItems="center">
        <Avatar sx={{ width: 34, height: 34, bgcolor: '#1769e0' }}>SW</Avatar>
        <Box><Typography variant="body2" fontWeight={700}>Savannah W.</Typography><Typography variant="caption" sx={{ color: '#9aa8c2' }}>Researcher</Typography></Box>
      </Stack>
    </Box>
  );
}
