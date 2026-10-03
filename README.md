# HATax

**Local individual income tax calculation aid.** Uses a local Python service and
browser workspace. Calculations are deterministic; optional explanations use
retrieved public IRS passages and a model running on this machine.

The public home page opens **HA Bookin’** or **HATax**. HATax starts with
**About you → Click your form → Form confirmation → Layout choice → Matching
box entry → State questions → Review**. Multiple W-2s and state rows are
supported; the limited federal estimate includes single-filer wages and
supported retirement distributions. Other boxes and complete tax treatment
remain unfinished. No complete return, official PDF export, document import,
or filing is available.

The standalone tax preview clears entries on refresh. The connected service
supports protected draft versions and reopening under the same MFA session as
Bookin’, when identity, database and document services are configured. Use
fictional information: hosted access, recovery and filing are not verified.

Built from the repository inventory in `HA_GitHub_IRS_100_Page_Inventory_2026-09-29.xlsx`,
following IRS rules as published. Covers federal Form 1040 core mechanics for
**TY2024, TY2025 and TY2026**, with a reference view of **all 50 states + DC**.

---

## ⚠ Read this first — limited status

| | |
|---|---|
| **What it is** | A local calculation aid with optional source-backed model explanations |
| **What it is not** | Tax advice · return preparation · filing |
| **Does it file** | **No.** No e-file, no MeF export, no transmission to the IRS or anywhere else |
| **Does it phone home** | **No.** The calculation path opens no network sockets |
| **Is it a complete return** | **No.** AGI is a *caller input*. See scope below |
| **TY2026** | Basic ordinary brackets and standard deductions updated from Rev. Proc. 2025-32; full return rules remain unverified |

### The verification ledger — please read

Rule values require independent verification. Some reference values have been
updated against primary IRS publications; that does not validate a complete
return. The engine defaults to reporting:

```
may_prepare_return = false
```

for **every** tax year. That is the correct state of a tool whose numbers have
not been checked, and it is deliberate.

To flip a year to reportable, open the cited revenue procedure, compare every
figure, and record the check in [`ha/rules/verification.json`](ha/rules/verification.json):

```json
"2025": {
  "verified": true,
  "checked_by": "your name",
  "checked_on": "2026-10-01",
  "against": "IRS Rev. Proc. 2024-40"
}
```

Rule files **cannot self-certify** — the ledger is the only input that can
raise `verified`. Until someone records a check, the engine refuses to report a
return as ready. See [`ha/engine/federal.py`](ha/engine/federal.py) and
[`tests/test_engines.py`](tests/test_engines.py) for how this is enforced.

---

## Run it

Zero dependencies. Python 3.10+ standard library only — no `pip install`.

```bash
python ha/server.py
# Home  http://127.0.0.1:8765/
# Tax   http://127.0.0.1:8765/tax
# API   http://127.0.0.1:8765/api/health
```

Binds to **loopback only** by default, so it is not reachable from your network.

### Connected public home, Bookin’ and HATax

```powershell
.venv/Scripts/python.exe -m ha.connected.server --port 8766
# Home    http://127.0.0.1:8766/
# Bookin  http://127.0.0.1:8766/connected.html
# HATax   http://127.0.0.1:8766/tax
```

Without configuration this opens a locked entrance and fictional stateless
HATax preview. It does not enable saving or sign-in. Configured protected access
requires the HTTPS setup in [CONNECTED-RUNBOOK.md](docs/CONNECTED-RUNBOOK.md).
The home chooser keeps both workspaces on the connected origin, including
when hosted. See [PUBLIC-WEBSITE.md](docs/PUBLIC-WEBSITE.md).

### Optional local IRS assistant

The default cards work without a downloaded model. For broader explanations,
install the source-ingestion dependencies from `requirements-connected.txt`,
run `python scripts/build_tax_library.py`, and make `qwen3:4b` available in
Ollama. Generation is opt-in with `HATAX_ENABLE_LOCAL_MODEL=1`; the first real
local-model test timed out after 90 seconds, so default source lookup returns
excerpts without invoking it. Restart the local server after configuration.
Public-source ingestion requires
internet access; runtime model requests go to `127.0.0.1:11434`.

The initial index contains 2025 IRS Publications 17, 334, 527 and Form 1040
instructions. Retrieval filters by tax year. Generated answers carry retrieved
source links and remain unverified; they cannot authorize return preparation.
All-year, state and Form 1041 source coverage is unfinished. See
[implementation references](docs/HATAX-BUILD-REFERENCES.md) for examples used,
checks performed and remaining work. Model files and the local source index
are ignored by Git and are not included in the DigitalOcean preview.

### Tests

```bash
python -m unittest discover -s tests -t .
# Current suite: 104 tests; database cases require the local test database.
```

Tests check selected scenarios and application behavior; they do not establish
independent tax certification. Some original assertions document their
arithmetic, so a failure shows the
calculation rather than two numbers disagreeing.

---

## What it computes

**Federal** — Form 1040 core only:

- Standard deduction and progressive bracket tax, 5 filing statuses × 3 years
- Preferential capital gains (0/15/20%) with correct band stacking
- Child tax credit with the `$50 per $1,000 **or fraction**` phase-out
- Earned income tax credit with **both** phase-out tests (earned income *and*
  AGI — the binding one governs)
- Marginal vs. effective rate

**State** — topology and refusal, not a 50-state calculator:

| Category | Count | Behavior |
|---|---|---|
| No wage income tax | 7 | Returns `0.00` + local-tax caveat |
| Investment-income-only (NH, TN) | 2 | **Refuses** — no figure, names the form |
| Levies income tax, brackets unloaded | 42 | **Refuses** — must-check list + DOR link |

## What it deliberately does *not* compute

Stated plainly because a tool that quietly skips these is worse than one that
admits it. Excluded:

- **AGI itself** — above-the-line adjustments are where returns go wrong
- Itemized deductions and the itemize-or-standard comparison
- Schedules 1–4 (self-employment, retirement contributions, HSA, alimony,
  student loan interest, other residence)
- AMT (Form 6251) · NIIT · Section 199A · Form 8962 repayment
- The ACTC+EITC special rule for 2021–2025
- All state and local tax beyond the seven zero-wage-tax jurisdictions
- **Municipal income tax** — NYC, Ohio municipalities, Maryland counties,
  Pennsylvania LEOST are outside scope entirely

Why no 50-state brackets: state income tax law is enacted and indexed
independently by each jurisdiction, often off a structure unrelated to the
federal one. Several deduct the federal income tax, several refund a state
EITC as a percentage of the federal credit, and a growing number add a
separate municipal layer. A static table that silently guesses in 41 states is
a liability, not a feature.

To enable a state, populate
`ha/rules/states.json → jurisdictions.<ST>.brackets.<year>` from that state's
DOR return instructions and set `data_complete: true`.

---

## Architecture

```
HAGHNESS/
├── ha/
│   ├── rules/          # JSON rule data — brackets, states, verification ledger
│   │   ├── federal.json        # TY2024/2025/2026 + provenance per block
│   │   ├── states.json         # 50 states + DC topology, special features
│   │   └── verification.json   # human check ledger — only path to verified
│   ├── engine/
│   │   ├── federal.py  # Decimal money, brackets, CTC, EITC, capital gains
│   │   └── states.py   # structured refusal for anything not sourced
│   ├── ai/
│   │   ├── kb.py       # 25 rule cards, each with citation + verified flag
│   │   └── assistant.py# Okapi BM25 retrieval + engine intents
│   ├── compliance/     # attestation, coverage report, review checklist
│   └── server.py       # stdlib HTTP server + JSON API
├── web/                # AIM-era client: buddy list, chat, calculator
├── tests/              # 45 hand-checked cases
└── ha/rules/*.json     # all statutory figures live in data, not code
```

### The local assistant

`ha/ai/` is a **knowledge base, not a language model.** Deterministic, offline,
and structurally unable to hallucinate a dollar figure: every sentence it emits
exists verbatim in a rule card or is assembled from an engine field.

- Okapi BM25 over card keywords and question variants
- Live intents: `what are my brackets`, `how much tax do i owe`, state lookups
- Every answer carries its citation and `verified` flag
- Out-of-scope questions → *"I will not improvise a tax answer"*

### API

| Route | |
|---|---|
| `GET /api/health` | liveness + version |
| `GET /api/attestation` | full limited-status, coverage, checklist |
| `GET /api/provenance` | per-year citations and verification state |
| `GET /api/brackets?year&status` | bracket table |
| `POST /api/calculate` | federal return (AGI required) |
| `POST /api/state` | state attempt (returns figure or refusal) |
| `GET /api/states` | all 50 + DC with computable flags |
| `POST /api/chat` | assistant turn |

---

## Provenance

| Year | Status | Authority |
|---|---|---|
| 2024 | Final law, **not yet checked by a human** | Rev. Proc. 2023-34 |
| 2025 | Final law, **not yet checked by a human** | Rev. Proc. 2024-40 |
| 2026 | Basic brackets/deductions updated; full return preparation blocked | Rev. Proc. 2025-32 |

Sub-rules flagged `verified: false` throughout: capital gains thresholds, CTC,
EITC. `ha/rules/verification.json` lists exactly what to confirm in each.

Source inventory: the 100-page GitHub repository inventory compiled
2026-09-29, and the five projects in its *Important missed* sheet.

---

## Data handling

All computation is local. Return inputs are held in process memory only: not
written to disk, not logged, not transmitted. The rule files are static JSON
containing no taxpayer data. No CDN, no external fonts, no analytics, no
third-party requests of any kind.

## License

See repository.
