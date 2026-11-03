"use client";
import { useLang } from "./I18n";

/** Translatable text leaf. The mockups carry only English + Arabic; other languages use the dictionary and fall back to English. */
export function T({ ar, children }: { ar: string; children: string }) {
  const { lang, dict } = useLang();
  if (lang === "ar") return <>{ar}</>;
  return <>{(lang !== "en" && dict[lang]?.[children]) || children}</>;
}
