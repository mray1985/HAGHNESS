# HATax form-first build — October 2, 2026

## User direction carried into this build

Collect client identity first. Then show “Click your form,” confirm W-2 before
layout selection, ask “Which one looks like yours?” and allow numbered-box
entry with a visible refund/balance estimate. Accept multiple W-2s and state
rows. Preserve the modern HATax brand; the calculator and assistant are supporting
tools at `/tools.html`. The user authorized implementation and creative decisions.

## Implemented behavior

- In-memory client setup: name, full address, SSN and birthday; single status.
- Searchable catalog sorted naturally, with unfinished forms explicitly unavailable.
- W-2 confirmation before standard/stacked layout choice.
- Boxes 1–8, 10–14, codes/checks and repeating state/local rows. The unused box 9
  has no input. The 2026 entry additionally captures the new box 14b occupation code.
- Multiple documents, layout changes, edits/removal and state-answer review.
- Debounced backend estimates with revision checks to discard stale responses.
- Estimate request projects only year, status, box 1 and box 2. Identity is neither
  stored in browser storage nor transmitted by this endpoint.
- Correct basic single deductions for 2024/2025/2026; ordinary bracket scenario,
  with withholding and refund/balance. Credits and all other tax components excluded.
- Default local source replies are excerpts. Qwen3:4b download completed, but a
  real source-backed answer timed out at 90 seconds and slowed this machine.
  Generation is therefore opt-in; performance and answer quality are unresolved.

## Research and design evidence

Official box labels checked against [2025 W-2](https://www.irs.gov/pub/irs-prior/fw2--2025.pdf)
and [2026 W-2](https://www.irs.gov/pub/irs-pdf/fw2.pdf). These code-native entry layouts
are not official filled IRS PDFs and cannot be filed. Basic 2025 deduction update
and 2026 reference: [Rev. Proc. 2025-32](https://www.irs.gov/irb/2025-45_IRB).
2024/2025 ordinary bracket citations are supplied separately by the estimator.

Design concept: `docs/design/hatax-w2-concept.png`. Primary design is white/navy/teal
with pale workflow and estimate rails, a ruled W-2 canvas, clear native inputs and
an adjacent running estimate. Existing standard-library service and native frontend
were retained instead of introducing a parallel framework/runtime.

Browser verification used the in-app browser, including 1504×1045 native-concept, 1440×1000 desktop and
390×844 phone dimensions. Screenshot captured through its screenshot API and
inspected with `view_image` alongside the generated reference. Comparison checks:

| Point | Implemented decision |
|---|---|
| Workflow/copy | Exact main instructions retained; confirmation precedes layout |
| Layout | Left numbered rail, central W-2, persistent right estimate |
| Palette | White canvas, navy type, teal controls, pale blue rails |
| Typography | Clear sans serif hierarchy and small numbered document labels |
| Document | Ruled cells and real editable fields; no screenshot used as UI |
| Responsive | Two-column document on phones; estimate fixed above bottom edge |
| Actions | State/another-W-2 actions in the rail and at document end |

Intentional differences from the visual concept: additional real W-2 boxes,
identity/control inputs, document-switch buttons, local columns and explicit scope
copy require a taller document. Calculated values replace fictional concept values.
Added copy is limited to these controls, local-preview/storage disclosure and
calculation exclusions. No marketing sections or fabricated metrics were added.
The design foundation was visually verified; exact image identity is not claimed.

## Verification and remaining work

104 tests passed with real PostgreSQL, including W-2 amounts, aggregation without
state double counting, blank inputs, rejected invalid/unbounded amounts, single-only
scope, HTTP response identity exclusion and non-generative excerpt mode. Browser
checks covered both layouts, multiple documents/states, preserved edits, refund and
balance changes, negative amount errors, state questions/review and phone overflow.
Fresh read-only review found no important defect in this flow; year-specific source
attribution was corrected.

Remaining: protected durable return drafts, document import, all other document
types, all filing statuses, eligibility/credits, additional W-2 treatments, state
engines, Form 1041, official PDF mapping/export, payment/refund/investment integration,
signature/security completion and filing. These are not presented as completed.
