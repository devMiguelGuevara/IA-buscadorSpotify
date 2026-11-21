// Compila la interfaz dentro del paquete de Python, para usar la app sin Node.
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "./",
  build: {
    outDir: "../banco_audio/app/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 4000,
  },
  server: {
    // En desarrollo, las llamadas a /api y /media van al servicio de Python.
    proxy: { "/api": "http://127.0.0.1:8765", "/media": "http://127.0.0.1:8765" },
  },
});
