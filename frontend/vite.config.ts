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
  },
});
