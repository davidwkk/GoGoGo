import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/auth": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
      "/chat": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
      "/trips": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
      "/users": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
});
