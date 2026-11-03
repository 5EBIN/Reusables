// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { I18nProvider } from "../components/I18n";
import { NavDrawer } from "../components/NavDrawer";

afterEach(cleanup);

const mount = (lang: "en" | "ar" = "en") => render(
  <I18nProvider initial={lang}>
    <div className="app">
      <nav className="sb"><a href="/overview">Overview</a><a href="/surveys">Surveys</a></nav>
      <NavDrawer />
    </div>
  </I18nProvider>,
);
const app = () => document.querySelector(".app")!;

describe("the menu button below 1100 px", () => {
  it("opens the sidebar, moves focus into it, and Escape closes it and returns focus to the button", () => {
    mount();
    const b = screen.getByRole("button", { name: "Menu" });
    expect(b.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(b);
    expect(b.getAttribute("aria-expanded")).toBe("true");
    expect(app().classList.contains("nav-open")).toBe(true);
    expect(document.activeElement).toBe(screen.getByRole("link", { name: "Overview" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(app().classList.contains("nav-open")).toBe(false);
    expect(document.activeElement).toBe(b);
  });
  it("closes on a link and on the backdrop; Tab wraps inside the open sidebar", () => {
    mount();
    const b = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(b);
    const last = screen.getByRole("link", { name: "Surveys" }); last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(screen.getByRole("link", { name: "Overview" }));
    fireEvent.click(last);
    expect(app().classList.contains("nav-open")).toBe(false);
    fireEvent.click(b);
    fireEvent.click(document.querySelector(".navbd")!);
    expect(app().classList.contains("nav-open")).toBe(false);
  });
  it("is labelled in Arabic", () => { mount("ar"); expect(screen.getByRole("button", { name: "القائمة" })).toBeTruthy(); });
});

describe("the stylesheet", () => {
  const css = readFileSync(resolve(__dirname, "../app/app.css"), "utf8");
  const narrow = css.slice(css.indexOf("Below 1100 px"));          // the rules this feature appended
  it("hides the button on a wide screen and places everything by logical side (right-to-left safe)", () => {
    expect(css).toMatch(/\.navbtn,\.navbd\{display:none\}/);
    expect(narrow).toContain("inset-inline-start");
    expect(narrow).not.toMatch(/(^|[;{])\s*(left|right):/);
    expect(narrow).toContain("[dir=rtl] .sb{transform:translateX(100%)}");
  });
});
