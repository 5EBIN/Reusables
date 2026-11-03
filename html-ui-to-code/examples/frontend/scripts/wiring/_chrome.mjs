// Shared sidebar + header: live organisation, user and badge counts. Everything is hidden/blank when the API is unavailable.
export default {
  extraData: { orgCount: "", signedIn: "", staff: "1", menu: "", unbuilt: "1" },
  imports: ['import { AvatarMenu } from "@/components/AvatarMenu";', 'import { OrgMenu } from "@/components/OrgMenu";', 'import { parseMenu } from "@/lib/menu-data";'],
  rules: [
    { sel: ".hd .search", show: "unbuilt" },                                          // not built: shown only with SHOW_UNBUILT_CONTROLS
    { sel: '.hd button[aria-label="Notifications"]', show: "unbuilt" },
    { sel: '.hd button[aria-label="Help"]', show: "unbuilt" },
    { sel: ".hd .org .av", bind: "orgInitials" },
    { sel: ".hd .org > span:nth-of-type(2)", bind: "orgName", after: '{d.signedIn ? <OrgMenu data={parseMenu(d.menu)} /> : null}' },
    { sel: ".hd .me .av", bind: "meInitials" },
    { sel: ".hd .me > span:nth-of-type(2)", bind: "meName", after: '{d.signedIn ? <AvatarMenu data={parseMenu(d.menu)} /> : null}' },
    { sel: 'a[href="approvals.html"] .badge', bind: "approvals", show: "approvals" },
    { sel: 'a[href="cx-cases.html"] .badge', bind: "cases", show: "cases" },
    { sel: 'a[href="platform-admin.html"]', show: "staff" },   // Acme staff only: the API answers 404 to everyone else, so the entry is not rendered at all
  ],
};
