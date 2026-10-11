import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "../components/Layout";
import ActivatePage from "../pages/ActivatePage";
import ChangePasswordPage from "../pages/ChangePasswordPage";
import HomePage from "../pages/HomePage";
import LoginPage from "../pages/LoginPage";
import UsersPage from "../pages/UsersPage";
import ProtectedRoute from "./ProtectedRoute";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/activate" element={<ActivatePage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <HomePage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/change-password"
        element={
          <ProtectedRoute>
            <Layout>
              <ChangePasswordPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/users"
        element={
          <ProtectedRoute roles={["SYSTEM_ADMIN"]}>
            <Layout>
              <UsersPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
