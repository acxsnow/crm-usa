import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "CRM Field Operations",
        short_name: "CRM Field Ops",
        theme_color: "#1e3a8a",
        display: "standalone",
        start_url: "/",
        icons: [],
      },
    }),
  ],
  resolve: {
    alias: { "@": "/src" },
  },
  server: {
    port: 5173,
    // Dev server runs inside Docker with the source bind-mounted from Windows;
    // inotify events don't cross that boundary, so poll or edits never reload.
    watch: { usePolling: true, interval: 500 },
    // La app llama a la API con una ruta relativa (/api/v1) y Vite la reenvía
    // al backend. Así funciona igual desde el celular en la red local (donde
    // "localhost" sería el propio teléfono) y no hay CORS en desarrollo.
    proxy: {
      "/api": {
        target: process.env.DEV_API_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
