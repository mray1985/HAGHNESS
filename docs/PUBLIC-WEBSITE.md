# HA public website

Built from connected commit 6d41900 on `codex/ha-public-website`. Approved
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
| `/index.html`, `/tax` | HATax workspace | Unavailable |
| `/connected.html` | Static file only; no connected API | Bookin’ entrance |
| `/api/connected/*` | Not implemented | Still requires authentication |

The chooser reads `/api/health` to identify the subsystem. On loopback it
links between standard ports 8765 and 8766 and explains when the other
server must be started. Hosted connected pages keep Bookin’ same-origin
and disable the unavailable HATax integration. Hosted pages never link
to a visitor's localhost. Unknown hosted status disables unavailable entrances.
Permission checks and secure session handling remain unchanged.

The existing connected-browser regression now opens `/connected.html`
explicitly because `/` is the public homepage. No deployment was performed.

## Accessibility

Semantic landmarks, one H1, skip link, visible focus, native disclosures,
reduced-motion support and native modal focus/escape behavior. Mobile columns
stack and navigation expands using a labeled button. Without JavaScript,
content, FAQ and section navigation remain usable with a visible fallback
preview section. JavaScript adds the chooser and server-aware destinations.
Nonstandard local ports require adjusting the cross-service chooser URLs.

## Verification

`tests/test_public_website.py` checks public access on both servers,
preservation of the tax workspace, and protected-data authentication.
`scripts/verify_public_website.cjs` checks responsive overflow, menu, FAQ,
modal escape/focus, preview paths, hosted unavailable states and no-JS content.
It needs Playwright and local servers on 8765/8766. An optional
`HA_BROWSER_EXECUTABLE` selects an installed Chromium-based browser.

October 2, 2026 checks: 100 tests discovered, 95 passed, five PostgreSQL
tests skipped because a disposable test database was not configured.
`git diff --check` and the browser script's JavaScript syntax check passed.
The browser script could not launch because this workspace has no installed
Playwright Chromium executable; rendered desktop/mobile verification remains
pending. These results do not verify filing readiness.

Database tests need `HA_TEST_DATABASE_URL` pointing only to a disposable
fictional database: their setup truncates fixture tables. They do not belong
against a real client database.
