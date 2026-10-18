import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// npm run dev (bez Dockera): żądania /api idą do API na localhost:3001.
// W obrazie produkcyjnym tę rolę pełni nginx (nginx/default.conf.template).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": "http://localhost:3001",
    },
  },
});
