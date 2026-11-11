import { Box, Button, Card, CardContent, Chip, Container, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";
import { texts } from "../content/texts";

export default function Academy() {
  return (
    <Box id="academy" sx={{ py: { xs: 6, md: 9 }, bgcolor: "#fff" }}>
      <Container maxWidth="lg">
        <SectionTitle label="آموزش" title={texts.academyTitle} sub={texts.academySub} />
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "repeat(3,1fr)" },
            gap: { xs: 2, md: 3 },
          }}
        >
          {texts.academy.map((a, i) => (
            <Reveal key={a.title} delay={i * 120} variant="up" sx={{ height: "100%" }}>
            <Card
              className="hover-lift card-shine"
              elevation={0}
              sx={{
                height: "100%",
                borderRadius: "18px",
                border: "1px solid #f3e2e7",
                position: "relative",
                overflow: "hidden",
                background: i === 1 ? "linear-gradient(165deg,#faf1f3,#f3eef7)" : "#fff",
              }}
            >
              <CardContent sx={{ p: { xs: 2.4, md: 3.2 } }}>
                <Chip
                  size="small"
                  label={a.tag}
                  sx={{
                    mb: 2, fontWeight: 700,
                    background: "linear-gradient(135deg,#fbe9ee,#efe9f5)",
                    color: "primary.main",
                  }}
                />
                <Typography variant="h6" fontWeight={800} gutterBottom>{a.title}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2 }}>
                  {a.desc}
                </Typography>
              </CardContent>
            </Card>
            </Reveal>
          ))}
        </Box>

        {/* فاز ۸۶ - لینک به ویترین فروش دوره‌ها (آکادمی رز) */}
        <Box sx={{ textAlign: "center", mt: { xs: 3.5, md: 5 } }}>
          <Button
            component={RouterLink}
            to="/academy"
            variant="contained"
            size="large"
            sx={{ borderRadius: 999, px: 4, fontWeight: 800 }}
          >
            مشاهده دوره‌های آکادمی رز
          </Button>
        </Box>
      </Container>
    </Box>
  );
}
