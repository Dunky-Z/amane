import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { tanstackRouter } from "@tanstack/router-vite-plugin";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), tanstackRouter()],
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "./src"),
    },
  },
  server: {
    // 监听全部网卡, 便于 NAS 远程开发时从 Windows 经局域网 IP 打开页面.
    // /api 仍代理到本机 uvicorn; API 不必对局域网暴露.
    host: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
