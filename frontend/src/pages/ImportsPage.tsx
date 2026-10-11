import {
  Alert, Box, Button, Chip, FormControl, FormControlLabel, InputLabel, MenuItem, Paper,
  Radio, RadioGroup, Select, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChangeEvent, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { commitImport, downloadTemplate, fetchImportJobs, previewImport } from "../api/imports";
import type { ImportPreview, ImportReport, ImportType } from "../api/imports";

const TYPE_LABELS: Record<ImportType, string> = {
  users: "کاربران",
  counselors: "مشاوران",
  applicants: "متقاضیان",
};

export default function ImportsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const roles = user?.roles ?? [];

  const availableTypes: ImportType[] = [];
  if (roles.includes("SYSTEM_ADMIN")) availableTypes.push("users", "counselors", "applicants");
  else if (roles.includes("ORG_MANAGER")) availableTypes.push("counselors", "applicants");
  else if (roles.includes("RECEPTION")) availableTypes.push("applicants");

  const [type, setType] = useState<ImportType>(availableTypes[0] ?? "applicants");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [strategy, setStrategy] = useState<"skip" | "update">("skip");
  const [error, setError] = useState<string | null>(null);

  const jobs = useQuery({ queryKey: ["imports"], queryFn: fetchImportJobs });

  const doPreview = useMutation({
    mutationFn: () => previewImport(type, file!),
    onSuccess: (res) => { setPreview(res); setReport(null); },
    onError: (e) => setError(errDetail(e)),
  });

  const doCommit = useMutation({
    mutationFn: () => commitImport(preview!.job_id, strategy),
    onSuccess: (res) => {
      setReport(res);
      setPreview(null);
      setFile(null);
      queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
    onError: (e) => setError(errDetail(e)),
  });

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setPreview(null);
    setReport(null);
    setError(null);
    setFile(e.target.files?.[0] ?? null);
  };

  return (
    <Stack spacing={3}>
      <Typography variant="h6" fontWeight={700}>ورود اکسل (بند ۸ سند)</Typography>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <Paper sx={{ p: 3 }}>
        <Stack spacing={2} direction={{ xs: "column", md: "row" }} alignItems={{ md: "center" }}>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>نوع ورود</InputLabel>
            <Select value={type} label="نوع ورود" onChange={(e) => { setType(e.target.value as ImportType); setPreview(null); setReport(null); setFile(null); }}>
              {availableTypes.map((t) => <MenuItem key={t} value={t}>{TYPE_LABELS[t]}</MenuItem>)}
            </Select>
          </FormControl>
          <Button variant="outlined" onClick={() => downloadTemplate(type)}>
            دانلود قالب {TYPE_LABELS[type]}
          </Button>
          <Button variant="outlined" component="label">
            انتخاب فایل xlsx
            <input type="file" accept=".xlsx" hidden onChange={onFileChange} />
          </Button>
          {file && <Chip label={file.name} onDelete={() => { setFile(null); setPreview(null); }} />}
          <Box flexGrow={1} />
          <Button variant="contained" disabled={!file || doPreview.isPending} onClick={() => doPreview.mutate()}>
            {doPreview.isPending ? "در حال بررسی…" : "بررسی و پیش‌نمایش"}
          </Button>
        </Stack>
        <Typography variant="caption" color="text.secondary">
          سقف: ۵ مگابایت و ۵۰۰۰ ردیف — ستون‌های شناسه باید قالب متن باشند — بدون فرمول.
        </Typography>
      </Paper>

      {preview && (
        <Paper sx={{ p: 3 }}>
          <Stack spacing={2}>
            <Typography variant="subtitle1" fontWeight={700}>پیش‌نمایش</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip label={`کل: ${preview.summary.total}`} />
              <Chip label={`معتبر: ${preview.summary.valid}`} color="success" />
              <Chip label={`خطادار: ${preview.summary.error}`} color="error" />
              <Chip label={`تکراری: ${preview.summary.duplicate}`} color="warning" />
            </Stack>

            {preview.errors.length > 0 && (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>ردیف</TableCell>
                      <TableCell>خطا</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {preview.errors.map((r) => (
                      <TableRow key={r.row_number}>
                        <TableCell>{r.row_number}</TableCell>
                        <TableCell>{r.error}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {preview.duplicates.length > 0 && (
              <>
                <Typography variant="subtitle2">تکراری‌ها (مطابق شناسه‌های موجود در سامانه):</Typography>
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>ردیف</TableCell>
                        <TableCell>رکورد موجود</TableCell>
                        <TableCell>فیلدهای قابل به‌روزرسانی</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {preview.duplicates.map((r) => (
                        <TableRow key={r.row_number}>
                          <TableCell>{r.row_number}</TableCell>
                          <TableCell>{r.existing_id?.slice(0, 8)}…</TableCell>
                          <TableCell>{r.will_update?.length ? r.will_update.join("، ") : "—"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
                <FormControl>
                  <RadioGroup row value={strategy} onChange={(e) => setStrategy(e.target.value as "skip" | "update")}>
                    <FormControlLabel value="skip" control={<Radio />} label="رد کردن تکراری‌ها" />
                    <FormControlLabel value="update" control={<Radio />} label="به‌روزرسانی فیلدهای مجاز" />
                  </RadioGroup>
                </FormControl>
              </>
            )}

            <Button variant="contained" color="primary" onClick={() => doCommit.mutate()} disabled={doCommit.isPending}>
              {doCommit.isPending ? "در حال ثبت…" : "تأیید و ثبت"}
            </Button>
          </Stack>
        </Paper>
      )}

      {report && (
        <Alert severity={report.errors > 0 ? "warning" : "success"}>
          گزارش ثبت: کل {report.total} | ایجاد {report.created} | به‌روزرسانی {report.updated} | ردشده {report.skipped} | خطا {report.errors}
        </Alert>
      )}

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={1}>عملیات‌های اخیر</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نوع</TableCell>
              <TableCell>فایل</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>کل</TableCell>
              <TableCell>ایجاد</TableCell>
              <TableCell>به‌روزرسانی</TableCell>
              <TableCell>رد</TableCell>
              <TableCell>خطا</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {jobs.data?.items.map((j) => (
              <TableRow key={j.id}>
                <TableCell>{TYPE_LABELS[j.import_type as ImportType] ?? j.import_type}</TableCell>
                <TableCell>{j.original_filename}</TableCell>
                <TableCell>
                  <Chip size="small" color={j.status === "committed" ? "success" : "warning"}
                    label={j.status === "committed" ? "ثبت‌شده" : "پیش‌نویس"} />
                </TableCell>
                <TableCell>{j.total_rows}</TableCell>
                <TableCell>{j.created_rows}</TableCell>
                <TableCell>{j.updated_rows}</TableCell>
                <TableCell>{j.skipped_rows}</TableCell>
                <TableCell>{j.error_rows}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Stack>
  );
}
