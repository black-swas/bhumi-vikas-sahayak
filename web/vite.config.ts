import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import prefixer from "postcss-prefix-selector";
import svgr from "vite-plugin-svgr";
import { defineConfig } from "vitest/config";
import {
  AGENT_SERVER_UI_SCOPE_SELECTOR,
  transformAgentServerUISelector,
} from "./src/styles/agent-server-ui-style-scope";

// The dev server proxies /api to the FastAPI backend. In production the API is same-origin
// (Vercel rewrites, or the backend serving web/build with SERVE_WEB=1), so no base URL is needed.
const API_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  server: {
    port: 3001,
    proxy: { "/api": { target: API_TARGET, changeOrigin: false } },
  },
  plugins: [!process.env.VITEST && reactRouter(), svgr(), tailwindcss()],
  resolve: { tsconfigPaths: true },
  css: {
    postcss: {
      plugins: [
        prefixer({
          prefix: AGENT_SERVER_UI_SCOPE_SELECTOR,
          transform(prefix: string, selector: string, prefixedSelector: string) {
            return transformAgentServerUISelector(prefix, selector, prefixedSelector);
          },
        }),
      ],
    },
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
