"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { RTL, type Lang } from "@/lib/lang";

export type Dict = Partial<Record<Lang, Record<string, string>>>;

type Ctx = { lang: Lang; setLang: (l: Lang) => void; dict: Dict };
const C = createContext<Ctx>({ lang: "en", setLang: () => {}, dict: {} });
export const useLang = () => useContext(C);

export function I18nProvider({ initial, dict = {}, children }: { initial: Lang; dict?: Dict; children: React.ReactNode }) {
  const [lang, set] = useState<Lang>(initial);
  const setLang = useCallback((l: Lang) => {
    set(l);
    document.documentElement.lang = l;
    document.documentElement.dir = RTL.has(l) ? "rtl" : "ltr";
    document.cookie = `lang=${l}; path=/; max-age=31536000; samesite=lax`;
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = RTL.has(lang) ? "rtl" : "ltr";
  }, [lang]);
  const v = useMemo(() => ({ lang, setLang, dict }), [lang, setLang, dict]);
  return <C.Provider value={v}>{children}</C.Provider>;
}
