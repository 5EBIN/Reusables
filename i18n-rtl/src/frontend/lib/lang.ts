export const LANGS = ["en", "ar", "ur", "hi", "ru", "fil"] as const;
export type Lang = (typeof LANGS)[number];
export const RTL: ReadonlySet<string> = new Set(["ar", "ur"]);
export const isLang = (x: unknown): x is Lang => typeof x === "string" && (LANGS as readonly string[]).includes(x);
