import { Box, Card, CardContent, Chip, Paper, Stack, Typography } from '@mui/material';

export default function SearchResults({ imagesToShow, selected, onSelect }) {
  return (
    <Card>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Typography fontWeight={900}>Search Results ({imagesToShow.length})</Typography>
          <Typography variant="body2" color="text.secondary">Sort by: Newest</Typography>
        </Stack>
        {imagesToShow.length === 0 ? (
          <Typography color="text.secondary">No images match the selected filters.</Typography>
        ) : (
          <Stack spacing={1.5}>
            {imagesToShow.map((item) => {
              const active = selected.id === item.id;
              return (
                <Paper key={item.id} onClick={() => onSelect(item)} sx={{ p: 1, cursor: 'pointer', border: active ? '2px solid #1769e0' : '1px solid #e2e8f0', bgcolor: active ? '#f4f8ff' : 'white', overflow: 'hidden', '&:hover': { borderColor: '#1769e0', bgcolor: '#f8fbff' } }}>
                  <Stack direction="row" spacing={1.25} alignItems="center">
                    <Box component="img" src={item.img} sx={{ width: 112, height: 82, objectFit: 'cover', borderRadius: 1, flexShrink: 0 }} />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography fontWeight={900} variant="body2" noWrap>{item.id}</Typography>
                      <Typography variant="caption" color="text.secondary" display="block">{item.date.replace(' UTC', '')}</Typography>
                      <Box sx={{ mt: 1, display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 40px', gap: 0.75, alignItems: 'center' }}>
                        <Chip size="small" color={item.color} label={item.label} sx={{ minWidth: 0, maxWidth: '100%', '& .MuiChip-label': { display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }} />
                        <Chip size="small" label={item.confidence} sx={{ width: 40, flexShrink: 0, fontWeight: 800, justifySelf: 'end' }} />
                      </Box>
                    </Box>
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}
