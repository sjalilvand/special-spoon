import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    // فاز ۷۶: تقسیم وندور — بهبود سرعت بارگذاری پنل در موبایل با کش پایدار
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom", "@tanstack/react-query"],
          // فاز ۷۷: @mui/icons-material عمداً خارج از وندور است — اگر در وندور باشد،
          // تمام آیکون‌های همهٔ ۵۰+ صفحه در بار اول eager دانلود می‌شوند؛ اکنون هر
          // آیکون همراه صفحهٔ خودش (lazy) بارگذاری می‌شود و آیکون‌های مشترک Layout
          // به‌صورت خودکار در chunk مشترک hoist می‌شوند.
          "vendor-mui": ["@mui/material", "@emotion/react", "@emotion/styled"],
        },
      },
    },
  },
});
