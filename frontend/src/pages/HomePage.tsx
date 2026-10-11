import { Chip, Container, Paper, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { apiClient } from "../api/client";

interface HealthResponse {
  status: string;
}

export default function HomePage() {
  const [apiStatus, setApiStatus] = useState<string>("در حال بررسی…");

  useEffect(() => {
    apiClient
      .get<HealthResponse>("/health")
      .then((res) => setApiStatus(res.data.status === "ok" ? "متصل" : "نامشخص"))
      .catch(() => setApiStatus("قطع"));
  }, []);

  return (
    <Container maxWidth="sm" sx={{ mt: 10 }}>
      <Paper elevation={3} sx={{ p: 5, textAlign: "center" }}>
        <Typography variant="h3" fontWeight={700} gutterBottom>
          Rosepsy
        </Typography>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          سامانه مشاوره روان‌شناختی سازمانی — RS-PS-04-01
        </Typography>
        <Stack direction="row" spacing={2} justifyContent="center" sx={{ mt: 4 }}>
          <Chip
            label={`وضعیت API: ${apiStatus}`}
            color={apiStatus === "متصل" ? "success" : "warning"}
          />
          <Chip label="فاز ۱ — اسکلت پایه" variant="outlined" />
        </Stack>
      </Paper>
    </Container>
  );
}
