"""HA Tax Software — compliance guardrails.

Two jobs.

1. Attach an auditable verification report to every return so a reviewer can
   see exactly which figures are final law, which are projections, and which
   sub-rules were never independently confirmed.
2. Make the limits of the tool impossible to miss: this is a calculation aid,
   it does not file, it does not transmit anything anywhere, and it is not
   return preparation under Circular 230 absent an authorized signer.
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from typing import Any

from ..rules import available_years, jurisdiction, unverified_items, year_block

SYSTEM_NAME = "HA Tax Software"
VERSION = "0.1.0"

DISCLAIMER_SHORT = (
    "Calculation aid only. Not tax advice. Does not file or transmit returns."
)

DISCLAIMER_FULL = f"""{SYSTEM_NAME} v{VERSION} — LIMITED STATUS

WHAT THIS IS
A local, offline individual income tax CALCULATION AID covering Form 1040
core mechanics for tax years 2024, 2025 and 2026, plus a reference view of
state individual income tax topology for all 50 states and the District of
Columbia.

WHAT THIS IS NOT
1. Not tax advice. Circular 230-covered advice requires a written opinion by
   a qualified individual. Nothing produced here is an opinion.
2. Not return preparation, and not authorized to prepare a return. A return
   signed or filed on the basis of this output alone is unauthorized practice.
3. Not a filing service. This software performs no transmission to the IRS or
   any third party. There is no e-file, no MeF export, and no network egress
   in the calculation path.
4. Not a complete return. AGI is a caller INPUT. The engine does not compute
   above-the-line adjustments, itemized deductions, Schedule 1-4 items, AMT,
   NIIT, Section 199A, or Form 8962 repayment. See engine/federal.py docstring.
5. Not final for TY2026. TY2026 figures are IRS PROJECTIONS published before
   the final revenue procedure exists. They will change and must not be used
   to prepare a return.
6. Not a state tax engine. Only the seven jurisdictions that levy no tax on
   wage income produce a figure. The other 43 return a structured refusal,
   including New Hampshire and Tennessee, which tax investment income.

DATA HANDLING
All computation is local. Return inputs are held in process memory only and
are not written to disk, not logged, and not transmitted. The bundled rule
files are static JSON under ha/rules/ and contain no taxpayer data.

EVIDENCE STANDARD
A rule block marked verified=false was transcribed from the cited authority
but has NOT been independently recomputed against the primary source. Treat
those figures as needing confirmation. See each calculation's
`verification` object for the specific list.
"""

DATA_HANDLING_STATEMENT = (
    "No taxpayer data leaves this machine. The calculation path opens no "
    "network sockets. Chat is handled in-process."
)


def environment() -> dict[str, Any]:
    return {
        "system": SYSTEM_NAME,
        "version": VERSION,
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "offline_by_design": True,
        "network_egress_in_calc_path": False,
    }


def rule_provenance() -> dict[str, Any]:
    """Per-year provenance, the human-check record, and what is unverified."""
    from ..rules import verification_ledger

    years: dict[str, Any] = {}
    for year in available_years():
        block = year_block(year)
        record = block.get("verification", {})
        years[year] = {
            "status": block.get("status"),
            "final": block.get("status") == "final",
            "citation": block.get("citation"),
            "human_checked": block.get("verified", False),
            "checked_by": record.get("checked_by"),
            "checked_on": record.get("checked_on"),
            "against": record.get("against"),
            "items_to_confirm": record.get("items_to_confirm", []),
            "unverified_items": unverified_items(block),
            "notes": block.get("notes"),
            "verification_note": block.get("verification_note"),
            "warnings": block.get("warnings", []),
            "filing_deadline": block.get("filing_deadline"),
            "extensions": block.get("extensions"),
        }
    return {
        "federal": years,
        "ledger": verification_ledger().get("_meta", {}),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def state_coverage() -> dict[str, Any]:
    """Which jurisdictions can produce a figure, and why the rest cannot."""
    from ..engine import states as state_engine

    rows = state_engine.list_jurisdictions()
    computable = [r["code"] for r in rows if r["computable"]]
    partial = [r["code"] for r in rows if r["partial"]]
    blocked = [r["code"] for r in rows if not r["computable"] and not r["partial"]]
    return {
        "total": len(rows),
        "computable": computable,
        "partial_investment_income_only": partial,
        "refused_pending_data": blocked,
        "counts": {
            "computable": len(computable),
            "partial": len(partial),
            "refused": len(blocked),
        },
        "statement": (
            "State income tax law is enacted and indexed independently by each "
            "jurisdiction. This build declines to return a number it cannot source. "
            "Local municipal taxes (NYC, Ohio municipalities, Maryland counties, "
            "Pennsylvania LEOST) are outside scope entirely."
        ),
    }


def review_checklist() -> list[dict[str, str]]:
    """The pre-filing checklist a reviewer should walk before trusting output."""
    return [
        {
            "id": "year-final",
            "check": "Tax year rule data is FINAL law, not a projection.",
            "how": "Read verification.year_final and verification.blockers on the return.",
        },
        {
            "id": "unverified",
            "check": "Every sub-rule listed in verification.unverified_items is confirmed "
                     "against the cited revenue procedure.",
            "how": "verification.unverified_items",
        },
        {
            "id": "agi-traced",
            "check": "AGI is traced to a signed return or ledger, not accepted from the UI.",
            "how": "This engine takes AGI as input. It does not derive it.",
        },
        {
            "id": "form-completeness",
            "check": "All Schedule 1-4 items, itemized deductions, and forms 6251, 8962, "
                     "and 199A considerations are handled outside this tool.",
            "how": "engine/federal.py module docstring lists every omission.",
        },
        {
            "id": "state",
            "check": "State and LOCAL tax handled for the correct county/city.",
            "how": "engine/states.py refuses where it cannot compute; municipal taxes are never modeled.",
        },
        {
            "id": "signer",
            "check": "An authorized signer has reviewed and approved the return.",
            "how": "This software is not return preparation. A signature requires a human preparer.",
        },
    ]


def attestation_payload() -> dict[str, Any]:
    """Machine-readable status block for the UI banner and API consumers."""
    coverage = state_coverage()
    prov = rule_provenance()
    final_years = [y for y, v in prov["federal"].items() if v["final"]]
    projected = [y for y, v in prov["federal"].items() if not v["final"]]

    return {
        "environment": environment(),
        "disclaimer_short": DISCLAIMER_SHORT,
        "disclaimer_full": DISCLAIMER_FULL,
        "data_handling": DATA_HANDLING_STATEMENT,
        "coverage": {
            "tax_years": available_years(),
            "final_years": final_years,
            "projected_years": projected,
            "states": coverage["counts"],
            "federal_scope": "Form 1040 core: standard deduction, ordinary brackets, "
                             "capital-gain stacking, CTC, EITC.",
        },
        "may_prepare_return_default": False,
        "filestransmits": False,
        "checklist": review_checklist(),
        "provenance": prov,
    }
