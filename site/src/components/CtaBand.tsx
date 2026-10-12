import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { texts } from "../content/texts";

export default function CtaBand() {
  return (
    <Box sx={{ background: "linear-gradient(135deg,#fdeef1 0%,#f6e2ef 100%)", py: 8 }}>
      <Container>
        <Stack spacing={2} alignItems="center" textAlign="center">
          <Typography variant="h4" fontWeight={800} color="primary.dark">
            {texts.ctaBand.title}
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 560 }}>
            {texts.ctaBand.sub}
          </Typography>
          <Button href="#consult" variant="contained" size="large" sx={{ mt: 1 }}>
            {texts.ctaBand.button}
          </Button>
        </Stack>
      </Container>
    </Box>
  );
}
