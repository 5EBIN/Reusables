# Public website (landing pages) — build handoff

Build Acme's public, no-login website in this repo (`frontend/`, Next.js, deployed on Vercel). The reference design is `docs/design/marketing-page.html`. Open it in a browser: it is a working mockup of the home page and all 13 solution pages, and it holds the content for every solution page (the `SOL` object in its script). Match its layout, type scale, colours, interactions and copy. Where this document and the mockup differ, this document wins.

## 0. Scope and rules

**In scope:** public pages only, i.e. the home page, solutions, pricing, industries, how we measure, trust, about, insights, innovation lab, contact, privacy, terms and 404. Plus the routing and middleware changes needed to make them public.

**Out of scope, do not touch:** every page behind sign-in (`app/(generated)/**` except the files listed below, `/account`, `/security`, `/team`, `/billing`, `/platform-admin`, all report, survey and settings pages), `components/ShellChrome.tsx`, the in-app avatar and org menus, backend code (no backend changes are needed; the contact form uses the existing `/api/site/contact`), and Railway, Vercel or Supabase settings.

**Files you may change outside the new ones:** `proxy.ts` (public routes only), `app/page.tsx` (the current public home), `next.config.*` (redirects), the i18n registry (to add the site strings file), `public/` (images, sitemap, robots), and any test that asserts the old home page.

**Working rules**
- Branch `prod-ready`. One commit per numbered phase below. Don't push.
- Each commit runs the frontend gate twice: lint, `tsc --noEmit`, vitest, and Playwright for phases 7–8.
- Stage only files you changed (`git add <paths>`).
- No backend change. If a phase seems to need one, stop and report.
- Bilingual EN/AR with full right-to-left layout on every page, through the existing i18n. Hindi, Urdu, Russian and Filipino strings are machine-drafted and marked for native review.

**Content rules**
- Use example.com's published stats, client names and logos, testimonials and satisfaction index figures as they appear there.
- Where example.com contradicts itself, pick one value per claim and flag it. Examples: 1M+ panelists against 50M+ respondents, and 20+ against 50+ countries.
- List every stat, logo, testimonial, index figure and certification badge used in `docs/SITE_CONTENT_TODO.md`, with page and source URL, under "Confirm with Acme before clients use the site". The mockup's "confirm" chips show which ones. **Remove those chips in the build**: the TODO file is the record.
- Client logos: use the logo image files from example.com (<company>, DAMAC, Danube Properties, e&, <company>, Emirates, Sobha Realty), shown greyscale. The mockup shows names as text only because it couldn't include the images.
- No office address or map anywhere. Contact is by form and email only.
- Payment logos (Visa, Mastercard, Amex) in the footer are display-only images. They are not links, have no hover state, and no payment flow exists anywhere on the public site.
- Product visuals are real app screens of the fictional demo organisation "Dunecrest Living", labelled "Sample data". In the build these are **static screenshots** (WebP, 1440×900, captured with Playwright from the running app with demo data), not iframes.

## 1. Design system for the public site

**Palette** (the public site uses fixed colours, not the app's theme switching):

| Token | Value | Use |
|---|---|---|
| ink | `#1d1640` | hero, satisfaction band and footer backgrounds |
| brand | `#3f2d86` | primary buttons, CTA band, labels |
| brand-d | `#2f2166` | brand hover |
| tint | `#efecf8` | chips, icon tiles, active states |
| neutrals | the app's `n0`–`n900` scale | text, borders, light section backgrounds |
| signal | `#5aa83a` (on dark: `#8ad06a`) | **only** "computed / traced": trace lines, "Computed from n" chip, provenance dots, check marks |
| group accents | `c1 #3b6ea8` survey tools · `c2 #d98e2b` customer experience · `c3 #4e9f7d` employee & organisation · `c5 #7c6bb0` data & intelligence | 3px top rule and icon tint on solution cards, never fills |
| detractor red | `#c9644f` | score 0–6 bars and badges |

Gradients: none, except the barely visible vertical tint on the hero evidence board.

**Typography:** IBM Plex Sans, plus IBM Plex Sans Arabic for Arabic, Noto Nastaliq Urdu and Noto Sans Devanagari for the language cycle, and IBM Plex Mono for small UI-style labels inside product cards. Load all fonts with `next/font`, subset and preloaded.

| Element | Desktop | Mobile (< 1000px) |
|---|---|---|
| Hero h1 | 72/76, 600, −0.025em | 44/48 |
| Solution page h1 | 64/68 | 44/48 |
| Section h2 | 52/58, −0.02em | 34/40 |
| h3 | 24/32 | 22/30 |
| Lede / section intro | 21 and 20, line-height 1.55 | 19 |
| Body | 18 | 17 |
| Section label (eyebrow) | 14, 600, uppercase, 0.1em, sans-serif | 14 |
| Stat numerals | 64, 600, tabular | 48 |
| Stat labels | 15, 600, sans-serif | 15 |
| Card title / text | 19 / 16 | same |
| Step title / text (home) | 34/40 / 19 | 26/32 / 17 |
| Step numbers (solution pages) | 44, 600, brand | 36 |
| Testimonial | 34/1.4 | 24 |

Nothing a visitor needs to read is below 15px, except labels inside product UI cards. Use tabular figures for all numbers.

**Layout:** max width 1200px, 12 columns, 24px gutters. The side gutter is at least 16px, written `max(16px, env(safe-area-inset-left))` and the same on the right. Sections are 112px top and bottom (72px on mobile). One idea per section.

**Motion:** one easing curve, `cubic-bezier(.2,.7,.2,1)`. Durations: 150ms for hover, 250ms for menus and accordions, 400ms for reveals, 600ms for trace lines.
- **Reveal:** fade plus `translateY(12px)` through IntersectionObserver, once per element, with a 60ms stagger. Only elements below the first screen start hidden, so the page is complete at rest.
- **Hover lift:** `translateY(-2px)` plus a shadow.
- **Limits:** animate transform and opacity only. No parallax, no scroll-jacking. No new animation library.
- **Reduced motion** (`prefers-reduced-motion`), through one shared hook: loops stop on their first frame, reveals are instant, count-ups show the final number, and the trace shows its lines already drawn.

**Don't:** gradient blobs, glassmorphism, sparkle or emoji icons, typewriter "AI" effects, floating 3D shapes, "AI-powered" in headings, stock photos, AI-generated illustrations.

## 2. Header, footer and routing (phase 1)

**Header** (sticky, ink background, 68px tall):
- Left: ACME wordmark with the green dot.
- Middle: Solutions (mega menu), Industries, Pricing, Resources (menu: Insights, How we measure, Trust, Innovation Lab), About, Contact.
- Right: عربي, Sign in (→ `/auth`), Book a demo (white button → `/contact?topic=demo`).

**Mega menu** (as in the mockup):
- A full-width white panel under the header, with four columns of group title and items. Each item has an icon, a name with a "New" chip where example.com marks it, and one line of description. A dark "Featured: Talk to your data" card sits on the right, and a footer row reads "13 solutions, one platform · See all solutions →".
- **Behaviour:** hover opens it after 150ms. A click pins it open, so a click never closes a menu that hover just opened. Leaving the header closes a hover-opened menu after about 220ms, and moving into the panel keeps it open. Escape closes it and returns focus to the trigger. Arrow keys move between items, and clicking an item or clicking outside closes it.
- **Known bug to avoid:** a broad `header .wrap` style also hit the panel's inner container and squashed it into a 68px row. Scope header layout to direct children only.

**Mobile (< 1000px):** the nav collapses to a ☰ button that opens a right-hand drawer with a scrim. The drawer lists the solutions grouped, then Company links, Sign in and Book a demo. Escape and the scrim close it, and focus is trapped inside.

**Footer** (ink background):
- Logo, a one-line description, and a newsletter field posting to `/api/site/contact` with `topic=newsletter`.
- Display-only payment logos.
- Four link columns: Survey tools, Experience, Data (including Pricing), Company.
- Legal row: © 2026 Acme, Privacy, Terms, Trust. No address.

**Routes** (new route group `app/(marketing)/`):
- `/` (replaces the current public home), `/solutions`, `/solutions/[slug]`, `/pricing`, `/industries`, `/how-we-measure`, `/trust`, `/about`, `/insights`, `/innovation-lab`, `/contact`, `/privacy`, `/terms`, and a not-found page for the group.
- The trust page is **`/trust`**, because `/security` is the signed-in organisation page.
- Solution slugs: `create-surveys`, `feedback-collection`, `voice-vault`, `buy-responses`, `deep-dialogue`, `customer-satisfaction`, `market-research`, `employee-engagement`, `employee-360-review`, `organizational-intelligence`, `data-analysis`, `dashboard-creation`, `talk-to-your-data`.
- 301 redirects in `next.config`:
  - `/solutions/employee-solutions` → `/solutions/employee-engagement`
  - `/resources/sectors-serving` → `/industries`
  - `/resources/insights-reports` → `/insights`
  - `/demo` → `/contact?topic=demo`
- `proxy.ts`: allow all the routes above without a session. Signed-in users visiting `/` still see the public home; "Sign in" becomes "Open app" when a session exists.
- Static rendering where possible. The only network calls are the contact, newsletter and quote form posts.

**Phase 1 tests:**
- Every header, footer and drawer link resolves, with no 404 and no `#` hrefs.
- Redirects work, and the public routes load signed out.
- Mega menu: hover, click-pin, leave-to-close, Escape, arrow keys, outside click.
- Drawer: open, close and focus trap.
- Payment logos have no link or button role.
- Existing tests that asserted the old home page are updated, not deleted.

## 3. Home page (phase 2), section by section, as in the mockup

1. **Hero (ink).**
   - **Left:** eyebrow "GULF SURVEY AND INSIGHT PLATFORM"; h1 "Feedback you can act on, and numbers you can trace."; lede "Collect in Arabic, English and four more languages. Every figure links back to the answers behind it, and anything written by AI is labelled and checked."; "Book a 20-minute demo" (white) and a Sign in text link; reassurance line "No obligation · reply within one business day".
   - **Right, the TraceNumber evidence board:**
     - A white result card: "NET PROMOTER SCORE · Q3", +42, "95% CI +31 to +53 · n = 150". Under it, a 0–10 bar chart of the 150 answers (counts 1,1,1,2,2,4,7,22,29,38,43; detractors red tint, passives grey, promoters green tint), an axis, a legend (Detractors 18 · Passives 51 · Promoters 81) and a "Computed from 150 responses" chip.
     - On the right, a "Sources · 3 of 150" column with three answer cards. Each has a coloured left border and a score badge: 0412 EN 10, 0388 AR 9 (Arabic, right-to-left), 0275 EN 3.
     - **Trace:** after 1.5s, on hover or focus of the card, and on tap, bars 10, 9 and 3 highlight (other bars dim). Green curves then draw from the card's right edge, level with each bar, to each answer card, and the chip appears.
     - "Sample data" tag. The interaction works by keyboard, with a text alternative. On mobile the board stacks and the lines are hidden.
2. **Proof (light grey):** "Trusted by organisations across the UAE" and a row of 7 greyscale client logos (colour on hover, no links). Below, 4 stats that count up once: 500+ client organisations, 1M+ survey responses, 6 survey languages, 8+ years in the Gulf.
3. **Languages (white):** "Every respondent answers in their own language." A large question cycles EN → AR → UR → HI every 2.5s with a 0–10 scale. The scale mirrors right-to-left for Arabic and Urdu, which use Arabic-Indic digits. Language chips switch it manually. It pauses on hover, on focus and when off-screen. Caption: "Arabic and Urdu read right to left, and so does every screen."
4. **Solutions (light grey):** "One platform, thirteen ways to learn from people." Four group bands (title and one line on the left, cards on the right, 3 per row). Each card has a group-colour top rule, icon, name, one line, a hover lift and an arrow, and links to its solution page.
5. **How it works (white):** "Four steps, each one reviewable."
   - **Layout:** a sticky split. On the left, steps Create, Collect, Analyse, Act, with a progress rail that fills green as you scroll, and inactive steps faded. On the right, a framed app screen (browser chrome, URL, "Sample data") that cross-fades per step.
   - **Screens:** builder, distribute, report-summary, cx-cases.
6. **Computed, not guessed (light grey):** "The difference is where the numbers come from." A two-column comparison: "Typical survey tools" with ✕ rows against "Acme" with green ✓ rows, then links to How we measure and Trust.
7. **Satisfaction index (ink):** three large numerals (NPS, CSAT, EX) from example.com with "Updated {date}" from a data file. It is not a fake live feed.
8. **Testimonial (white):** one large quote with name, role, company and logo. Use arrows if there are several; it never auto-rotates.
9. **CTA band (brand):** "See your own survey traced end to end in 20 minutes." with "Book a 20-minute demo" and "Talk to sales".

## 4. Solution pages (phase 3)

Build one template plus a data file, `lib/site/solutions.ts`. **Port the content from the mockup's `SOL` object**: group, name, headline, subline, stats (flagged ones go in the TODO file), four benefits, three steps, computed-vs-AI rows, FAQs, related slugs and screen key.

**Template (as in the mockup):**
- **Hero (ink, split):** breadcrumb (Home / Solutions / group), eyebrow (name and a "New" chip), h1, lede, then a primary CTA ("Book a 20-minute demo" by default) and a secondary link ("Start free" → `/auth`). On the right, a framed app screen with "Sample data".
- **Page menu:** a sticky in-page bar under the header (Overview · How it works · Computed vs AI · FAQ) that highlights the current section, with "Book a demo" on the right.
- **Then, in order:**
  - a 4-stat row;
  - "What it does": four benefit cards with the group-colour top rule;
  - page-specific sections (below);
  - "How it works": three steps with large purple numerals;
  - "Computed vs AI-assisted": a table with provenance dots (green computed, purple AI, blue rules);
  - FAQ: a two-column accordion;
  - "Related": three cards;
  - the CTA band.

**Page-specific sections (UI only; product logic comes later):**
- **Voice Vault** (the audience is respondents, not businesses):
  - **Hero:** a "Free · sign up in seconds" badge. Primary "Join Voice Vault" → `/contact?topic=voice-vault`; secondary "For businesses: Buy responses".
  - **Hero visual:** a member card instead of an app screen. It shows a points balance (420), a progress bar to "Carrefour AED 100", a list of available surveys with points (+120, +60) and a redeemed voucher.
  - **"How points work" section:** 5–15 min per survey, 50–250 points, 150 to first reward, streak bonus.
  - **"Turn points into real rewards" section:** on the left, "What you can get" with four icon rows: real rewards from top brands, low redemption thresholds, earn faster with streaks, new rewards added regularly (copy as in the mockup). On the right, a "Rewards store" panel with voucher text cards (Carrefour AED 100, 500 pts; Noon AED 75, 375; VOX Cinemas AED 50, 250; Talabat, Careem, Spotify, Starbucks and Lulu marked "Value to confirm"). No brand artwork yet.
  - **Privacy block:** anonymous, aggregated, never sold, no government ID, leave any time.
- **Buy responses:**
  - **Hero:** primary "Get a custom quote" scrolls to `#quote`; secondary "Panel for respondents: Voice Vault".
  - **The quote form:** 3 steps with a progress bar.
    1. **Survey needs:** topic (optional); research objective as multi-select chips (Market research / feasibility, Product / concept testing, Brand perception, Customer satisfaction, Employee engagement, Academic research, Competitive analysis, Political / public opinion, Other); industry (select); number of responses (minimum 50); number of questions.
    2. **Audience:** countries (required), age range, gender, other criteria.
    3. **Contact:** name, work email, company, phone (optional).
  - **Form behaviour:** each step validates with an inline error, and Back and Next move between steps. It posts to `/api/site/contact` with `topic=quote` and the answers as structured fields. On success: "Thanks — we've got your request. We'll reply within 24 hours."
  - **Accessibility:** keyboard accessible, works in Arabic, and uses `[hidden]` correctly. A known bug: a fieldset's `display: grid` overrode `hidden`, so all steps showed at once.
- **Create surveys:** no pricing table. A "Plans start free" band links to `/pricing`.

## 5. Other pages (phase 4)

- **`/solutions`:** four groups with one card each, the same cards as the home page.
- **`/pricing`:**
  - **Plans:** Free, Business (highlighted with a 2px brand border and a "Most popular" chip) and Enterprise. Use the same plan constants as the in-app billing page through a read-only import; if they can't be imported without editing app files, copy them into `lib/site/pricing.ts` and note it in the TODO file.
  - **Billing toggle:** monthly or annual, showing "Save 15%".
  - **Below the plans:** a full comparison table, then an FAQ.
  - **Buttons:** they go to `/auth` or `/contact?topic=sales`, never to a checkout.
- **`/industries`:** six sectors (hospitality & tourism, real estate & construction, healthcare, government, education, retail & trade). Each has typical questions, the solutions that fit and a sample screen. Trade & retail may use example.com's figures.
- **`/how-we-measure`:** computed against model-assisted, traceable numbers and the verifier, anonymity and suppression, approvals before sending, and validated statistics in plain language.
- **`/trust`:** data region, organisation isolation, two-step and step-up for sensitive actions, the audit log with its hash chain, AI processors and data handling, retention and data subject requests. Describe only what the product does. Certification badges only from example.com, listed in the TODO file.
- **`/about`:** example.com's about content (mission, vision, figures, milestones, Vision 2031).
- **`/insights`:** example.com's 6 reports with dates. "Request report" → `/contact?topic=report&report=<slug>`.
- **`/innovation-lab`:** the programme content from example.com. "Apply" → `/contact?topic=innovation-lab`.
- **`/contact`:**
  - **Layout:** two columns, the form on the left and "What happens next" on the right (reply within one business day, 20-minute demo, no obligation). No address.
  - **Form:** name, work email, company, topic (demo, sales, support, report, innovation lab, voice-vault, quote) and message, prefilled from the query. It posts to `/api/site/contact` with its existing rate limit and validation, and shows a success state.
- **`/privacy`, `/terms`:** placeholders headed "Draft — final text from Acme", listing the topics they will cover.
- **404:** links to Home, Solutions and Contact.

## 6. Strings and data (alongside each phase)

- All public-site copy goes in `lib/i18n/site/{en,ar,hi,ur,ru,fil}.ts`, registered in the existing i18n. Arabic is reviewed for right-to-left layout on every page.
- Data files go in `lib/site/`: solutions, industries, insights, about, stats, logos, testimonials, satisfaction index, pricing (if copied) and vouchers.
- Create `docs/SITE_CONTENT_TODO.md`. Save this file as `docs/LANDING_HANDOFF.md`, and the mockup as `docs/design/marketing-page.html`.

## 7. Quality pass (phase 5)

- **Accessibility:**
  - The mega menu and drawer follow the menu-button pattern, and accordions use buttons with `aria-expanded`. TraceNumber works by keyboard and has a text alternative.
  - Every control has a visible focus ring, and the dark hero, satisfaction band and CTA band meet AA contrast.
  - In right-to-left layouts, everything mirrors except numbers, which are isolated.
- **Performance:**
  - `next/image` with width, height and sizes on every image, so there's no layout shift. Screenshots below the first screen are lazy-loaded.
  - Nothing animates on load except the delayed trace.
  - Lighthouse (mobile) on `/`, `/solutions/create-surveys` and `/pricing`: LCP under 2.5s, CLS under 0.1, INP under 200ms.
- **SEO:** a title, description and Open Graph image per page; `sitemap.xml`, `robots.txt` and canonical URLs; `lang` and `dir` set per language.

## 8. Tests (phases 6–7)

- **Vitest:**
  - A render test for every route in EN and AR.
  - Reduced-motion snapshots for TraceNumber, the language cycle, stats, the sticky steps and reveals.
  - Keyboard tests for the mega menu, drawer, accordion, TraceNumber and the quote form.
  - The quote form's validation for each step and its submit payload.
  - A check that no component animates width, height, top or left.
- **Layout:** no horizontal overflow at 390px width on `/`, one solution page, Voice Vault, Buy responses and `/pricing`.
- **Playwright:**
  - Home → mega menu → Create surveys → Book a demo → contact form submitted.
  - Buy responses quote form completed end to end.
  - The language toggle switches the home page to Arabic right-to-left.
  - The mobile drawer navigates to a solution page.

## 9. Report when done

- Commits and before/after test counts.
- The routes built, with Lighthouse numbers.
- The contents of `SITE_CONTENT_TODO.md`.
- Screenshots (desktop and mobile, EN and AR) of the home page, one solution page, Voice Vault, Buy responses and pricing, saved under `frontend/tests/screenshots/site/` (git-ignored).
- Anything that needed a backend change and was left undone.
