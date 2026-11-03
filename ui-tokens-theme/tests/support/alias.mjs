// `await import("./support/alias.mjs")` at the top of a test file, before importing app code that uses the `@/` alias.
import { register } from "node:module";

register("./aliasHook.mjs", import.meta.url);
