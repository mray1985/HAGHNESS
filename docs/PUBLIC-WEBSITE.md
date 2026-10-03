# HA public website

Public assets originated on `codex/ha-public-website` at 908ef3f and are now
integrated into the current connected branch without replacing its backend. Approved
scope: home, services, how Bookin’ connects to HATax, and entrances to the
existing previews. No hosted identity, storage, filing or payments added.

## Design

Warm ivory #f6f5ef, forest teal #123e35, ink #163a32, citrus #e4f195 and coral
#df785e. Arial/Helvetica headings and body pair with Georgia for product
names, the paper panel and italic “life.” No external fonts, trackers or
third-party assets. Order: navigation, hero, people-first statement,
products, record/connect/review workflow, educational guides, FAQ, purpose and footer.

“Learn with HA” contains four original guides: record income and expenses,
pay estimated taxes as income comes in, review records throughout the year,
and address missing receipts. Each uses a concrete example and next step.
Native disclosures work with keyboard input and without JavaScript. The
tax and recordkeeping guides link to IRS sources and show a review date;
the estimated-tax guide identifies 2026, while the product workflow is
labeled as a development goal. The IRS allows more frequent estimated
payments when enough is paid by the required deadlines. Reserve balances
are distinguished from completed payments. Quarterly bookkeeping totals
are distinguished from the unequal estimated-tax payment periods.

Content is original HA writing. Intuit’s article index informed the idea
of organizing educational topics; its article text and branding were not
copied. Source review date: October 2, 2026.

The user revised the bottom heading to **“Good help brings understanding.”**
That supersedes the initial generated concept. Other deliberate deviations:
goal wording for the incomplete Bookin’/HATax connection, a third FAQ about
that connection, HA's coral punctuation, and a functional preview chooser.
The ledger is semantic HTML with vector icons, not a raster screenshot.

## Routes

| Address | Tax server | Connected server |
|---|---|---|
| `/`, `/home`, `/home.html` | Public website | Public website |
| `/home.css`, `/home.js` | Public assets | Explicitly allowed public assets |
| `/index.html`, `/tax` | Standalone HATax workspace | HATax with current protected draft integration |
| `/connected.html` | Static file only; no connected API | Bookin’ entrance |
| `/api/connected/*` | Not implemented | Still requires authentication |

The chooser reads `/api/health` and requires `tax_workspace: true` before
advertising the tax workspace. The connected service offers both destinations
on the same origin; its existing session protects records and draft saving.
A standalone loopback tax service links to the separate Bookin’ service at
port 8766 and explains that it must be started. Hosted standalone services
hide the unavailable Bookin destination. A failed health check disables both
chooser destinations. Hosted visitors never receive localhost links.

Root/home routes are public; authentication, callback destination, permission,
CSRF and protected API handling remain unchanged. Both workspace brands return
to HA home. The connected-browser regression opens `/connected.html` explicitly.
No deployment was performed. Public copy reflects the connected local prototype,
while complete taxes, filing, payments and hosted recovery remain unfinished.

## Accessibility

Semantic landmarks, one H1, skip link, visible focus, native disclosures,
reduced-motion support and native modal focus/escape behavior. Mobile columns
stack and navigation expands using a labeled button. Without JavaScript,
content, FAQ and section navigation remain usable with a visible fallback
preview section. JavaScript adds the chooser and server-aware destinations.
Nonstandard local ports require adjusting the cross-service chooser URLs.

## Verification

`tests/test_public_website.py` checks both public roots, aliases, current tax
navigation, capabilities and unauthenticated protected-data denial.
`scripts/verify_public_website.cjs` checks desktop/390/320px rendering, guides,
keyboard input, menu, FAQ, modal escape/focus, both workspaces, hosted synthetic
capability/failure states and no-JS content. It needs existing Playwright and a
Chromium-based browser (`HA_BROWSER_EXECUTABLE`). Optional `HA_TAX_URL` and
`HA_BOOKS_URL` allow isolated local services; cross-service default remains 8766.
`HA_SCREENSHOT_DIR` captures desktop/mobile evidence without taxpayer data.

Browser plugin not available in this session; regular Playwright with installed
Edge was used. Public previews were served by real isolated loopback Python
servers. Hosted capability cases use synthetic health responses; they do not
prove hosted operation or sign-in. Protected MFA save/reopen evidence is tracked
separately in the Day 8 audit. No external fonts, trackers or third-party assets
were added.

Source links were rechecked October 3, 2026:
- [IRS recordkeeping](https://www.irs.gov/businesses/small-businesses-self-employed/what-kind-of-records-should-i-keep)
- [IRS estimated taxes](https://www.irs.gov/businesses/small-businesses-self-employed/estimated-taxes)
- [IRS records reconstruction](https://www.irs.gov/tax-professionals/eitc-central/recordkeeping)

Database regressions use only the existing isolated fictional PostgreSQL fixture.
They must never run against real client records.

October 3 integration results: 288 tests ran with the isolated real Windows
PostgreSQL fixture: 284 passed, four Linux-only cleanup checks skipped.
The public-site Edge journey passed desktop, 390px and 320px checks, both current
workspace routes, keyboard/dialog controls, no-JS content and synthetic hosted
capability failures. Screenshot evidence: [desktop](screenshots/public-website-desktop.png)
and [mobile](screenshots/public-website-mobile.png).

The extended real Keycloak/nginx/PostgreSQL/ClamD browser journey also passed
starting at public home → preview chooser → locked Bookin → password/OTP →
protected books/documents/HATax save/reopen → logout denial. Its browser portion
measured 7.0 seconds for one automated fictional local run, excluding fixture
startup and OTP waits. This is not a customer completion-time promise. The
owned Linux fixture services stopped afterward; nginx watched temporary activity
was absent and inherited request logs empty. Evidence:
KEYCLOAK-NGINX-SESSION-EVIDENCE.json. Self-signed browser trust, hosted access,
Spaces, complete tax calculations and filing remain unverified. Independent
review found no important routing/security regressions.

Standalone viewing command: `.venv/Scripts/python.exe -m ha.server 127.0.0.1 8770`,
then open `http://127.0.0.1:8770/` or `/tax`. A preview with that command was started
for this session; after it stops, run the command again. Connected configuration
and HTTPS instructions remain in CONNECTED-RUNBOOK.md.
