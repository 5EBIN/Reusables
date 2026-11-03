import { parseDocument } from "htmlparser2";
import { describe, expect, it } from "vitest";
// @ts-expect-error untyped build script
import { convertPage } from "../scripts/lib/convert.mjs";

const html = `<body><main class="page"><div class="a"><b>mock</b></div><p>keep</p></main><nav class="sb"></nav></body>`;
const conv = (wiring: unknown) => convertPage(parseDocument(html, { lowerCaseTags: false, lowerCaseAttributeNames: false, decodeEntities: true }), "x", wiring);

describe("wiring DSL: swap", () => {
  it("renders the original element unless `when` holds, and the replacement when it does", () => {
    const { tsx } = conv({ extraData: { live: "" }, rules: [{ sel: ".a", swap: "<Live />", when: "d.live === '1'" }] });
    expect(tsx).toContain(`{d.live === '1' ? (<Live />) : (<div className="a"><b>mock</b></div>)}`);
    expect(tsx).toContain("<p>keep</p>");
  });

  it("composes with other rules on the same element (they apply to the fallback only)", () => {
    const { tsx } = conv({ extraData: { live: "", t: "" }, rules: [{ sel: ".a b", bind: "t" }, { sel: ".a", swap: "<Live />", when: "d.live", attrs: { onClick: "go" } }] });
    expect(tsx).toMatch(/\{d\.live \? \(<Live \/>\) : \(<div className="a" onClick=\{go\}><b>\{d\.t\}<\/b><\/div>\)\}/);
  });

  it("passes `loader: \"params\"` through to the page generator", () => {
    expect(conv({ loader: "params", extraData: { live: "" } }).loader).toBe("params");
    expect(conv({ loader: true }).loader).toBe(true);
    expect(conv(null).loader).toBe(false);
  });
});
