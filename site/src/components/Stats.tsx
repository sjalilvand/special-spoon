import { Box, Container, Stack, Typography } from "@mui/material";
import { texts } from "../content/texts";

export default function Stats() {
  return (
    <Box sx={{ background: "linear-gradient(135deg,#3d1e26 0%,#5a2a35 60%,#4d3a52 100%)", py: { xs: 5, md: 6 } }}>
      <Container>
        <Stack direction="row" spacing={{ xs: 3, md: 6 }} justifyContent="center" flexWrap="wrap" useFlexGap>
          {texts.stats.map((s) => (
            <Box key={s.label} sx={{ textAlign: "center", minWidth: 150 }}>
              <Typography variant="h3" fontWeight={800} sx={{ color: "#f2cdd5", fontSize: { xs: 30, md: 40 } }}>{s.n}</Typography>
              <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.85)" }}>{s.label}</Typography>
            </Box>
          ))}
        </Stack>
      </Container>
    </Box>
  );
}
