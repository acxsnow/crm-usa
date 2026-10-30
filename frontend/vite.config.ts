import fs from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// HTTPS solo en desarrollo y solo si se pide (DEV_HTTPS=1): el celular no
// entrega el GPS a una página http que no sea localhost. El certificado lo
// genera `scripts/dev-cert.sh` (autofirmado, en `.certs/`, fuera de git); el
// teléfono muestra un aviso la primera vez y hay que aceptarlo.
const https =
  process.env.DEV_HTTPS === "1" && fs.existsSync(".certs/dev.key")
    ? { key: fs.readFileSync(".certs/dev.key"), cert: fs.readFileSync(".certs/dev.crt") }
    : undefined;

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // Ícono de la «P» de la marca (public/): al agregarla a la pantalla de
      // inicio se abre sola, sin la barra del navegador.
      includeAssets: ["icon.svg", "apple-touch-icon.png"],
      manifest: {
        name: "PAP CRM",
        short_name: "PAP CRM",
        description: "CRM y operación en campo de Delta HVAC",
        lang: "es",
        theme_color: "#ffffff",
        background_color: "#ffffff",
        display: "standalone",
        orientation: "portrait",
        start_url: "/",
        icons: [
          { src: "pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512.png", sizes: "512x512", type: "image/png" },
          { src: "maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      // En desarrollo también, para poder instalarla desde el celular contra el servidor local.
      devOptions: { enabled: true },
    }),
  ],
  resolve: {
    alias: { "@": "/src" },
  },
  server: {
    port: 5173,
    https,
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
