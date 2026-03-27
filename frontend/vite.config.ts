import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  publicDir: resolve(__dirname, "../data"),
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});