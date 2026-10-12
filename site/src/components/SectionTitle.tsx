import { Stack, Typography } from "@mui/material";

export default function SectionTitle({
  label, title, sub, light = false,
}: {
  label: string;
  title: string;
  sub?: string;
  light?: boolean;
}) {
  return (
    <Stack spacing={1} alignItems="center" mb={5}>
      <Typography
        variant="caption"
        sx={{
          background: light ? "rgba(255,255,255,0.2)" : "linear-gradient(135deg,#fde7ec 0%,#f0e6f6 100%)",
          color: light ? "#fff" : "primary.main",
          px: 2.5, py: 0.6, borderRadius: 99, fontWeight: 700,
          border: light ? "none" : "1px solid #f6d7de",
        }}
      >
        {label}
      </Typography>
      <Typography
        variant="h3"
        fontWeight={800}
        textAlign="center"
        className={light ? "" : "grad-text"}
        color={light ? "#fff" : undefined}
      >
        {title}
      </Typography>
      {sub && (
        <Typography
          variant="body1"
          sx={{ maxWidth: 620, textAlign: "center", color: light ? "rgba(255,255,255,0.9)" : "text.secondary" }}
        >
          {sub}
        </Typography>
      )}
    </Stack>
  );
}
