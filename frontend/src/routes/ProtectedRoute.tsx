import { Box, CircularProgress, Typography } from "@mui/material";
import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function ProtectedRoute({
  children,
  roles,
}: {
  children: ReactNode;
  roles?: string[];
}) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress />
      </Box>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  if (roles && !roles.some((r) => user.roles.includes(r))) {
    return (
      <Box p={4}>
        <Typography color="error">دسترسی مجاز نیست.</Typography>
      </Box>
    );
  }
  return <>{children}</>;
}
