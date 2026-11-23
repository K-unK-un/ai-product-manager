import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // 绑定所有网卡，局域网其他设备可通过 http://<本机IP>:5173 访问
    port: 5173,
    proxy: {
      // 本地开发：API 请求转发到后端
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
