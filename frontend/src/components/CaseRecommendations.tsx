import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Paper, Stack, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  createRecommendation, fetchCaseRecommendations, publishRecommendation,
} from "../api/recommendations";
import type { RecommendationRow } from "../api/recommendations";
import { formatJalaliDateTime } from "../utils/jalali";

export default function CaseRecommendations({ caseId }: { caseId: string }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const isCounselor = (user?.roles ?? []).includes("COUNSELOR");

  const [open, setOpen] = useState(false);
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", caseId],
    queryFn: () => fetchCaseRecommendations(caseId),
  });

  useEffect(() => {
    if (open) { setContent(""); setError(null); }
  }, [open]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["recommendations", caseId] });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (content.trim().length < 3) {
      setError("متن توصیه را وارد کنید");
      return;
    }
    try {
      await createRecommendation(caseId, content.trim());
      setOpen(false);
      invalidate();
    } catch (err) {
      setError(errDetail(err));
    }
  };

  const doPublish = async (row: RecommendationRow) => {
    if (!window.confirm("انتشار این توصیه؟ پس از انتشار در پنل متقاضی نمایش داده می‌شود.")) return;
    setError(null);
    try {
      await publishRecommendation(row.id);
      invalidate();
    } catch (err) {
      setError(errDetail(err));
    }
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="subtitle1" fontWeight={700}>توصیه‌ها (بالینی)</Typography>
        {isCounselor && (
          <Button size="small" variant="contained" onClick={() => setOpen(true)}>توصیه جدید</Button>
        )}
      </Box>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {isLoading && <CircularProgress size={24} />}
      <Stack spacing={1}>
        {data?.items.length === 0 && (
          <Typography variant="body2" color="text.secondary">توصیه‌ای ثبت نشده است.</Typography>
        )}
        {data?.items.map((row) => (
          <Box key={row.id} sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 1.5 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Chip size="small" color={row.is_published ? "success" : "default"}
                label={row.is_published ? "منتشرشده" : "پیش‌نویس"} />
              {row.is_published && (
                <Typography variant="caption" color="text.secondary">
                  {row.published_at ? formatJalaliDateTime(row.published_at) : ""}
                </Typography>
              )}
              <Box flexGrow={1} />
              {isCounselor && !row.is_published && (
                <Button size="small" variant="outlined" onClick={() => doPublish(row)}>انتشار</Button>
              )}
            </Stack>
            <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}>{row.content}</Typography>
          </Box>
        ))}
      </Stack>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <form onSubmit={submit}>
          <DialogTitle>توصیه جدید</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              این توصیه ابتدا به‌صورت پیش‌نویس ثبت می‌شود و تنها پس از «انتشار» صریح،
              در پنل متقاضی نمایش داده می‌شود (بند ۹.۳).
            </Typography>
            {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
            <TextField
              autoFocus fullWidth multiline minRows={4} margin="normal"
              label="متن توصیه *"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              required
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOpen(false)}>انصراف</Button>
            <Button type="submit" variant="contained">ثبت پیش‌نویس</Button>
          </DialogActions>
        </form>
      </Dialog>
    </Paper>
  );
}
