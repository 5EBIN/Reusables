// Copies the design system stylesheet VERBATIM into the app. A test asserts the bytes are identical.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../docs/design/assets/app.css");
const dst = resolve(here, "../app/app.css");
mkdirSync(dirname(dst), { recursive: true });
copyFileSync(src, dst);
console.log("synced app.css");
