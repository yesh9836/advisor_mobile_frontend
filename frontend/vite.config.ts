import path from "node:path";
import { sentryVitePlugin } from "@sentry/vite-plugin";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const sentryAuthToken = process.env.SENTRY_AUTH_TOKEN;
const sentryOrg = process.env.SENTRY_ORG;
const sentryProject = process.env.SENTRY_PROJECT;
const sentryRelease = process.env.VITE_SENTRY_RELEASE ?? process.env.SENTRY_RELEASE;

const plugins = [react()];

if (sentryAuthToken && sentryOrg && sentryProject && sentryRelease) {
  plugins.push(
    sentryVitePlugin({
      authToken: sentryAuthToken,
      org: sentryOrg,
      project: sentryProject,
      release: {
        name: sentryRelease,
      },
      sourcemaps: {
        assets: "./dist/**",
      },
      errorHandler: (error) => {
        throw error;
      },
      telemetry: false,
    }),
  );
}

export default defineConfig({
  plugins,
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    include: ["src/test/**/*.{test,spec}.{ts,tsx}"],
  },
});
