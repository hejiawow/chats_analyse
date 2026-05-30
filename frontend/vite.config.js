import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        "@": resolve(__dirname, "src"),
      },
    },
    server: {
      host: '0.0.0.0',  // 允许内网访问
      port: 5173,
      proxy: {
        "/api": {
          target: env.VITE_API_URL || "http://localhost:8010",
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: resolve(__dirname, "dist"),
      assetsDir: "assets",
      emptyOutDir: true,
    },
  };
});
