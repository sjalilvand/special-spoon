import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: {
    // فاز ۷۶ (v0.59.0): تقسیم وندور برای کش پایدار در موبایل — کتابخانه‌های
    // بزرگ در chunk جدا نگه داشته می‌شوند تا تغییر صفحه‌ها، دانلود مجدد آنها
    // را لازم نکند و بار اول سریع‌تر باشد.
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-mui": ["@mui/material", "@emotion/react", "@emotion/styled"],
        },
      },
    },
  },
});
