import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Make the /data folder (from repo root) available as static assets
  publicDir: "../data",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
