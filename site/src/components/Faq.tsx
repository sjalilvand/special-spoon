import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { useState } from "react";
import SectionTitle from "./SectionTitle";
import { texts } from "../content/texts";

export default function Faq() {
  const [openIdx, setOpenIdx] = useState<number | null>(0);

  return (
    <Box id="faq" sx={{ py: { xs: 6, md: 9 }, bgcolor: "#fff" }}>
      <Container maxWidth="md">
        <SectionTitle label="سوالات" title={texts.faqTitle} sub={texts.faqSub} />
        <Stack spacing={1.6}>
          {texts.faq.map((f, i) => {
            const open = openIdx === i;
            return (
              <Paper
                key={f.q}
                elevation={0}
                onClick={() => setOpenIdx(open ? null : i)}
                sx={{
                  cursor: "pointer",
                  border: "1px solid #f3e2e7",
                  borderRadius: "16px",
                  p: { xs: 2.2, md: 2.8 },
                  background: open ? "linear-gradient(160deg,#fdf6f7,#ffffff)" : "#fff",
                  transition: "background .25s ease",
                }}
              >
                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
                  <Typography variant="subtitle1" fontWeight={800} color={open ? "primary.main" : "text.primary"}>
                    {f.q}
                  </Typography>
                  <Box
                    sx={{
                      width: 30, height: 30, flexShrink: 0, borderRadius: "50%",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      bgcolor: open ? "primary.main" : "#faeef1",
                      color: open ? "#fff" : "primary.main",
                      fontWeight: 800, fontSize: 18,
                      transition: "all .25s ease",
                      transform: open ? "rotate(45deg)" : "none",
                    }}
                  >
                    +
                  </Box>
                </Box>
                {open && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1.6, lineHeight: 2.1 }}>
                    {f.a}
                  </Typography>
                )}
              </Paper>
            );
          })}
        </Stack>
      </Container>
    </Box>
  );
}
