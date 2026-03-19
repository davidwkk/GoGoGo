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
      "/auth": "http://localhost:8000",
      "/chat": "http://localhost:8000",
      "/trips": "http://localhost:8000",
      "/users": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
