import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/icon-192.png", "icons/icon-512.png"],
      workbox: {
        navigateFallback: "/index.html",
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        // Ensure clients pick up new bundles after deploy (PWA was stuck on old JS).
        clientsClaim: true,
        skipWaiting: true,
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // Small GridFS JPEG thumbs — stale-while-revalidate for gallery speed
            urlPattern: ({ url }) =>
              /\/api\/media\/[^/]+\/thumb/.test(url.pathname),
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "wan-thumbs",
              expiration: { maxEntries: 128, maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
          {
            // Full media and other API — always hit network
            urlPattern: ({ url }) =>
              url.pathname.startsWith("/api") ||
              url.hostname.includes("onrender.com") ||
              url.hostname.includes("trycloudflare.com"),
            handler: "NetworkOnly",
          },
          {
            urlPattern: ({ request }) => request.destination === "image",
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "wan-images",
              expiration: { maxEntries: 64, maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
        ],
      },
      manifest: {
        name: "Wan Studio",
        short_name: "Wan",
        description: "Image and video generation — jobs keep running on the server",
        theme_color: "#0c0f0e",
        background_color: "#0c0f0e",
        display: "standalone",
        orientation: "portrait-primary",
        start_url: "/",
        scope: "/",
        lang: "en",
        icons: [
          {
            src: "icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
