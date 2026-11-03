import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import routes from "../app/(generated)/routes.json";
import { findAll, tokens } from "./helpers/normalize";

const design = resolve(__dirname, "../../docs/design");
const load = (n: string) => import(`../app/(generated)/${n}/content.tsx`);

describe("every mockup renders 1:1 (same element tree, classes, text, attributes)", () => {
  for (const r of routes) {
    it(`${r.name}`, async () => {
      const html = readFileSync(resolve(design, `${r.name}.html`), "utf8");
      const Content = (await load(r.dir)).default;
      const rendered = renderToStaticMarkup(<Content />);
      const want = tokens(html, (doc) => {
        // shell pages: <main class="page"> plus the drawers/modals the mockup places next to .app
        if (r.shell) return findAll(doc, (e) => (e.name === "main" && (e.attribs.class ?? "").split(" ").includes("page")) || ((e.parent as any)?.name === "body" && e.name !== "script" && !(e.name === "div" && (e.attribs.class ?? "").split(" ").includes("app"))));
        return findAll(doc, (e) => e.name === "body")[0].children;
      });
      const got = tokens(rendered, (doc) => doc.children);
      expect(got.length).toBeGreaterThan(5);
      expect(got).toEqual(want);
    });
  }
});
