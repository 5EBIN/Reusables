// The English source of every interface-string table, in one place (used by tests and by scripts/i18n-export.ts). Pure data, no React.
import { DIST_AR, DIST_EN } from "@/components/distribute/strings";
import { INTERVIEW_EN } from "@/components/interview/strings";
import { A_EN, A_AR } from "@/lib/authoring-messages";
import { INTERVIEW_AR } from "@/components/interview/strings";
import { D_EN as MSG_D_EN, D_AR as MSG_D_AR } from "@/lib/msg-d";
import { E_EN, E_AR } from "@/lib/messages-e";
import { MESSAGES_AR, MESSAGES_EN } from "@/lib/messages";
import { REPORTS_AR, REPORTS_EN } from "@/lib/messages-reports";
import { RUNNER_AR, RUNNER_EN } from "@/lib/runner/strings";
import { SITE_AR } from "./site/ar";
import { SITE_EN } from "./site/en";
import type { TableId } from "./locales";

type Tbl = Readonly<Record<string, string>>;
export const CATALOG_EN: Record<TableId, Tbl> = {
  messages: MESSAGES_EN, d: MSG_D_EN, e: E_EN, reports: REPORTS_EN, authoring: A_EN as Tbl, distribute: DIST_EN as Tbl, runner: RUNNER_EN as Tbl, interview: INTERVIEW_EN as Tbl, site: SITE_EN,
};
export const CATALOG_AR: Record<TableId, Tbl> = {
  messages: MESSAGES_AR, d: MSG_D_AR, e: E_AR, reports: REPORTS_AR, authoring: A_AR as Tbl, distribute: DIST_AR as Tbl, runner: RUNNER_AR as Tbl, interview: INTERVIEW_AR as Tbl, site: SITE_AR,
};
