# HATax example-driven implementation

User requested current visual styling, corrected brackets/controls, wider tax knowledge and researched frontend/backend code examples on October 2, 2026.

## Examples read and applied

- W3C APG manual-activation tabs: https://www.w3.org/WAI/ARIA/apg/patterns/tabs/examples/tabs-manual/ . Applied tab/panel relationships, selected state, one tab stop, Left/Right/Home/End focus navigation, native button activation. Browser testing remains necessary; this does not assert universal assistive-technology compliance.
- US Web Design System tables: https://designsystem.digital.gov/components/table/ . Applied caption, column-header scope, readable numeric alignment and explicit taxable-income ranges. The app does not copy US government branding or claim USWDS certification.
- OWASP server input validation: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html . Applied JSON object, question/context type and finite-number validation to the legacy API. Negative HTTP tests require JSON 400 errors.
- Ollama local model and embeddings APIs: https://docs.ollama.com/api/chat and https://docs.ollama.com/capabilities/embeddings . Reference for a retrieval-backed local assistant, not authority for tax rules. Ollama is installed locally. The loopback adapter is implemented; its model download and actual generated-answer evaluation remain pending.
  Follow-up: implemented the loopback model adapter and SQLite FTS retrieval library. Downloaded/indexed 2025 Publications 17, 334, 527 and Form 1040 instructions, preserving URLs, PDF page numbers and SHA256 hashes in the ignored local manifest. Qwen3:4b model download is in progress; no actual generated-answer quality verification yet. Library tests use an explicitly synthetic transport and enforce year filtering and returned-source IDs. Generated content always remains unverified and cannot authorize preparation. Model download alone does not complete universal tax coverage.
- IRS Rev Proc 2025-32: https://www.irs.gov/irb/2025-45_IRB . Corrected final 2026 basic standard deductions and ordinary brackets for all supported statuses. Final publication does not establish full return readiness.
- IRS Topic 415: https://www.irs.gov/taxtopics/tc415 . Added the Augusta/augsta answer with residence qualification, annual fewer-than-15-day limit, rental-expense exclusion and a separate business-deduction review question.

## Changes and reproducible checks

HATax replaces visible HAGHNESS Tax branding. New modern.css provides the responsive interface. Reproduced the overlap before fixing it: #messenger display:grid overrode hidden, leaving Messenger visible behind other panels. Explicit hidden semantics prevent that. Collapse, focus and return buttons now change actual workspace state; bracket navigation loads data. Chat and reference use consistent over/through bracket bounds rather than subtracting one dollar.

`scripts/verify_legacy_browser.cjs` checks exclusive panels, bracket loading, collapse/restore, phone-width overflow and page errors using a real browser. `tests/test_review_regressions.py` includes final 2026 reference and Augusta typo tests; both failed before implementation. `scripts/update_2026_reference.py` records the primary-source transcription.

## Broad tax-assistant requirement remains incomplete

A finite rule-card collection cannot answer every tax detail. A language model alone cannot guarantee tax accuracy either. Required build: a versioned federal/state/1040/1041 source registry; approved public-source ingestion with hashes and effective dates; retrieval that filters jurisdiction/year; local model explanations tied to retrieved passages; links/page references; factual follow-up questions; unknown-topic tracking; independent tax boundary evaluations; and current-source update workflow. Keep calculation and filing authorization outside model-generated decisions.

Do not use current cards as a verified generative corpus: the external review identified unresolved CTC guidance and other inaccuracies. Broader corpus ingestion and model evaluation still need implementation. The Augusta answer fixes the demonstrated gap; it does not complete universal tax coverage.

The library uses only retrieved official PDF passages rather than feeding the legacy cards to the model. The initial source coverage is 2025 federal individual/business/rental rules, not all years/states/1041 subjects. Broader questions can use the library while exact curated questions retain their existing route. Existing card accuracy still needs repair. Legacy malformed-object, numeric and question-type handling was also fixed; negative HTTP regression checks require JSON errors instead of disconnected responses.

Rebuild public-source library with `.venv/Scripts/python.exe scripts/build_tax_library.py` (network needed for public PDFs only). Run Ollama with `qwen3:4b` available, then restart `python -m ha.server`. Runtime prompts go only to 127.0.0.1:11434; ingestion downloads public IRS documents. The DigitalOcean preview does not deploy this local library/model, and broad hosted inference is not configured.

Fresh code review found that marking the whole 2026 ruleset final overstated the publication status of untouched components. Repaired this with a partial year status and a separate final basic-bracket status. Full calculation output retains an incomplete/projected warning; basic bracket references display their final IRS publication correctly. Contradictory old year warnings were removed.

Verification: 97 tests passed with real local PostgreSQL and no skipped database tests. Browser checks passed for exclusive panels, bracket loading, collapse/focus/return controls, keyboard tabs, Augusta typo response, mobile overflow and page errors. These checks establish application behavior, not independent tax certification or generated-answer quality.
