import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./", import.meta.url)) } },
  test: { environment: "node", include: ["tests/**/*.test.{ts,tsx}"], setupFiles: ["./tests/setup.ts"], globals: true, testTimeout: 30000, env: { NEXT_PUBLIC_SHOW_UNBUILT_CONTROLS: "1", NEXT_PUBLIC_SUPABASE_URL: "https://stub.supabase.test", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_test" } },
});
