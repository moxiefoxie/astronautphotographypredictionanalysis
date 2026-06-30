import { Box, Button, Card, CardContent, Typography } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import PlaceIcon from '@mui/icons-material/Place';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';

export default function QuickActions() {
  return (
    <Card>
      <CardContent>
        <Typography fontWeight={900} sx={{ mb: 1.5 }}>Quick Actions</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1 }}>
          <Button size="small" variant="outlined" startIcon={<BookmarkBorderIcon />}>Add to Collection</Button>
          <Button size="small" variant="outlined" startIcon={<DownloadIcon />}>Download Image</Button>
          <Button size="small" variant="outlined" startIcon={<PlaceIcon />}>View on Map</Button>
          <Button size="small" variant="outlined" startIcon={<CompareArrowsIcon />}>Compare</Button>
        </Box>
      </CardContent>
    </Card>
  );
}
