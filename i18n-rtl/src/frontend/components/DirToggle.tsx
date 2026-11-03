"use client";
import { useLang } from "./I18n";

/** Same button as the mockup (#dirToggle): switches English <-> Arabic and the document direction. */
export function DirToggle({ title }: { title?: string }) {
  const { lang, setLang } = useLang();
  const ar = lang === "ar";
  return (
    <button className="btn sm" id="dirToggle" title={title} onClick={() => setLang(ar ? "en" : "ar")}>
      {ar ? "EN" : "عربي"}
    </button>
  );
}
