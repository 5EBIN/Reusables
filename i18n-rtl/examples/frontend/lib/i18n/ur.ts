// MACHINE-DRAFTED, NEEDS NATIVE REVIEW: Urdu interface strings were drafted without a native speaker. See docs/I18N.md for the review checklist.
import type { Locale } from "./locales";
import { SITE_UR } from "./site/ur";
import { AUTHORING_1 } from "./ur/authoring-1";
import { AUTHORING_2 } from "./ur/authoring-2";
import { D } from "./ur/d";
import { DISTRIBUTE_1 } from "./ur/distribute-1";
import { DISTRIBUTE_2 } from "./ur/distribute-2";
import { E, REPORTS } from "./ur/e-reports";
import { MESSAGES_1 } from "./ur/messages-1";
import { MESSAGES_2 } from "./ur/messages-2";
import { MESSAGES_3, T } from "./ur/misc";
import { INTERVIEW, RUNNER } from "./ur/respondent";

const locale: Locale = {
  t: T,
  msgs: {
    messages: { ...MESSAGES_1, ...MESSAGES_2, ...MESSAGES_3 }, d: D, e: E, reports: REPORTS,
    authoring: { ...AUTHORING_1, ...AUTHORING_2 }, distribute: { ...DISTRIBUTE_1, ...DISTRIBUTE_2 }, runner: RUNNER, interview: INTERVIEW, site: SITE_UR,
  },
};
export default locale;
