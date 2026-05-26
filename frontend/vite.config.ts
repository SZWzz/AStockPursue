/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import fs from "fs";

const PROXY_PATHS = [
  "/v1",
  "/runs",
  "/sessions",
  "/swarm/presets",
  "/swarm/runs",
  "/settings/llm",
  "/settings/data-sources",
  "/correlation",
  "/upload",
  "/shadow-reports",
  "/alpha",
  "/indicator-lab",
  "/strategy-lab",
  "/stock",
  "/admin",
  "/api",
];

function readVersion(): string {
  try {
    return fs.readFileSync(path.resolve(__dirname, "../VERSION"), "utf-8").trim();
  } catch {
    return "0.0.0";
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_URL || "http://localhost:8899";
  const __APP_VERSION__ = JSON.stringify(readVersion());

  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") },
    },
    define: {
      __APP_VERSION__,
    },
    server: {
      port: 5899,
      proxy: Object.fromEntries(
        PROXY_PATHS.map((p) => [p, { target: apiTarget, changeOrigin: true }]),
      ),
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      globals: true,
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            "vendor-react": ["react", "react-dom", "react-router-dom"],
            "vendor-charts": ["echarts"],
          },
        },
      },
    },
  };
});
