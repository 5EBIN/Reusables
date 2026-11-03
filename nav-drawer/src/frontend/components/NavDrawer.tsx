"use client";
import { useEffect, useRef, useState } from "react";
import { useMsg } from "@/lib/messages";

/** Below 1100 px the sidebar (`.sb`) is hidden by app.css; this is its way back: a menu button in the header corner that slides the same sidebar in from the start side.
 *  Closes on a link, on Escape and on the backdrop; Tab stays inside while it is open. The button and backdrop do not exist (display:none) on a wide screen. */
export function NavDrawer() {
  const t = useMsg();
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const app = () => btn.current?.closest(".app") ?? null;

  useEffect(() => {
    const root = app(); const sb = root?.querySelector<HTMLElement>(".sb");
    if (!root || !sb) return;
    root.classList.toggle("nav-open", open);
    if (!open) return;
    const items = () => [...sb.querySelectorAll<HTMLElement>("a[href]")];
    items()[0]?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); btn.current?.focus(); return; }
      if (e.key !== "Tab") return;
      const all = items(); const first = all[0], last = all[all.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    const click = (e: MouseEvent) => { if ((e.target as HTMLElement).closest("a[href]")) setOpen(false); };
    document.addEventListener("keydown", key); sb.addEventListener("click", click);
    return () => { document.removeEventListener("keydown", key); sb.removeEventListener("click", click); root.classList.remove("nav-open"); };
  }, [open]);

  return (
    <>
      <button ref={btn} type="button" className="navbtn" aria-label={t("nav_menu")} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <svg className="i" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
      </button>
      <div className="navbd" onClick={() => { setOpen(false); btn.current?.focus(); }} aria-hidden="true" />
    </>
  );
}
