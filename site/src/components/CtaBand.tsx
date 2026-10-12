import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { texts } from "../content/texts";

export default function CtaBand() {
  return (
    <Box sx={{ background: "linear-gradient(135deg,#b04a5a 0%,#7a5c8a 100%)", py: 9 }}>
      <Container>
        <Stack spacing={2} alignItems="center" textAlign="center">
          <Typography variant="h3" fontWeight={800} color="#fff">
            {texts.ctaBand.title}
          </Typography>
          <Typography variant="body1" sx={{ maxWidth: 560, color: "rgba(255,255,255,0.9)" }}>
            {texts.ctaBand.sub}
          </Typography>
          <Button
            href="#consult"
            size="large"
            sx={{
              mt: 1.5, bgcolor: "#fff", color: "primary.main", fontWeight: 800,
              px: 4, "&:hover": { bgcolor: "#fde7ec" },
            }}
          >
            {texts.ctaBand.button}
          </Button>
        </Stack>
      </Container>
    </Box>
  );
}
