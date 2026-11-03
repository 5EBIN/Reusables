import { loadChrome, loadMe, nudgeFrom } from "@/lib/loaders/chrome";
import { ImpersonationBanner } from "./ImpersonationBanner";
import { MfaGate } from "./MfaGate";
import { NavDrawer } from "./NavDrawer";
import { Header, Sidebar } from "./ShellChrome";

/** One backend call (GET /v1/me) for the whole chrome and the two-step reminder. The page started its own data before this renders, and its content streams in behind the shell. */
export async function Shell({ active, children }: { active: string; children: React.ReactNode }) {
  const me = await loadMe();
  const d = await loadChrome(me);
  const nudge = nudgeFrom(me);
  return (
    <div className="app">
      <Sidebar active={active} d={d} />
      <NavDrawer />
      <div className="main">
        <ImpersonationBanner />
        <Header d={d} />
        {nudge && <MfaGate nudge={nudge} />}
        {children}
      </div>
    </div>
  );
}
