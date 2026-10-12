import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { SUGGESTED } from "../content/assets";
import { texts } from "../content/texts";

export default function Services() {
  return (
    <Container id="services" sx={{ py: 8 }}>
      <Typography variant="h4" fontWeight={800} color="primary.main" mb={4} textAlign="center">
        {texts.servicesTitle}
      </Typography>
      <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={3}>
        {texts.services.map((s, idx) => {
          const icon = SUGGESTED.icons[idx] ?? null;
          return (
            <Paper key={s.title} elevation={2} sx={{ p: 3 }}>
              <Stack direction="row" spacing={2} alignItems="flex-start">
                <Box sx={{ fontSize: 40, lineHeight: 1 }}>
                  {icon ? <Box component="img" src={icon} alt={s.title} sx={{ height: 52 }} /> : s.emoji}
                </Box>
                <Box>
                  <Typography variant="h6" fontWeight={700} color="primary.main">
                    {s.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>
                    {s.desc}
                  </Typography>
                </Box>
              </Stack>
            </Paper>
          );
        })}
      </Box>
    </Container>
  );
}
