"""HA Tax Software — state engine.

This build computes state tax ONLY for jurisdictions that both (a) levy no
individual income tax on wages, and (b) are flagged data_complete in
ha/rules/states.json. For every other jurisdiction it returns a structured
REFUSAL carrying the state-specific features a preparer must check.

That is the whole design. State tax law is not a national dataset: 41 states
and DC each enact, index, sunset, and amend independently, many off the
federal bracket structure entirely, and a growing number levy a separate
municipal tax the federal return never sees (NYC, Ohio municipalities, MD
counties, PA LEOST). A 50-state engine built from a static table would be a
50-state engine that is silently wrong in every state it claims to cover.

Wire your verified per-year bracket data into
ha/rules/states.json -> jurisdictions.<ST>.brackets.<year> and set
data_complete=true to enable that state.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..rules import D, jurisdiction, money, states as _state_table


#: Jurisdictions levying no tax on ordinary wage/salary income.
#: NH and TN are deliberately NOT here: both tax interest and dividends.
_WAGE_INCOME_TAX_FREE = {
    "AK": "No individual income tax.",
    "FL": "No individual income tax.",
    "NV": "No individual income tax. (Commerce tax applies to businesses.)",
    "SD": "No individual income tax.",
    "TX": "No individual income tax. (Texas uses margin/franchise tax on businesses.)",
    "WA": "No individual income tax. State capital gains tax repealed effective 2025 — verify.",
    "WY": "No individual income tax.",
}

#: States that appear zero-tax but are not. These get a dedicated warning.
_INTEREST_DIVIDEND_ONLY = {
    "NH": (
        "New Hampshire levies NO tax on wages, salaries, or active service income, "
        "but DOES tax interest, dividends, and capital gains (Form I-1128). "
        "A filer with investment income only may still have an NH return. "
        "Legislative phase-out of this tax has been under active consideration — "
        "verify current status with the NH Department of Revenue."
    ),
    "TN": (
        "Tennessee levies NO tax on wages or salaries, but DOES tax interest and "
        "dividends as Hall Income Tax (Form TI-102). The rate is 6.5% and is not "
        "indexed. Verify whether it remains in effect for the tax year."
    ),
}


def list_jurisdictions() -> list[dict[str, Any]]:
    """Every jurisdiction with enough metadata to render the UI selector."""
    rows = []
    for code, entry in _state_table()["jurisdictions"].items():
        rows.append({
            "code": code,
            "name": entry["name"],
            "income_tax": entry["income_tax"],
            "type": entry["type"],
            "top_rate": entry.get("top_rate"),
            "computable": code in _WAGE_INCOME_TAX_FREE,
            "partial": code in _INTEREST_DIVIDEND_ONLY,
            "data_complete": entry.get("data_complete", False),
            "source_url": entry.get("source_url"),
            "special_features": entry.get("special_features", []),
            "notes": entry.get("notes"),
        })
    rows.sort(key=lambda r: r["name"])
    return rows


def detail(code: str) -> dict[str, Any]:
    """Full entry for one jurisdiction, including why it can or cannot compute."""
    entry = jurisdiction(code)
    code_key = _find_code(code)
    computable = code_key in _WAGE_INCOME_TAX_FREE

    payload: dict[str, Any] = {
        "code": code_key,
        "name": entry["name"],
        "income_tax": entry["income_tax"],
        "type": entry["type"],
        "top_rate": entry.get("top_rate"),
        "data_complete": entry.get("data_complete", False),
        "source_url": entry.get("source_url"),
        "special_features": entry.get("special_features", []),
        "notes": entry.get("notes"),
        "computable": computable,
        "refusal": None,
    }

    if computable:
        payload["state_tax"] = 0.0
        payload["explanation"] = _WAGE_INCOME_TAX_FREE[code_key]
        return payload

    if code_key in _INTEREST_DIVIDEND_ONLY:
        payload["refusal"] = "PARTIAL — not zero-tax"
        payload["explanation"] = _INTEREST_DIVIDEND_ONLY[code_key]
        payload["state_tax"] = None
        return payload

    features = entry.get("special_features", [])
    payload["refusal"] = "NOT COMPUTABLE — bracket data not loaded"
    payload["state_tax"] = None
    payload["explanation"] = (
        f"{entry['name']} levies an individual income tax. This build does not ship "
        f"verified per-year brackets for it, so no figure is produced. "
        f"Recorded top marginal rate for orientation: "
        f"{entry['top_rate'] * 100:.2f}%." if entry.get("top_rate")
        else f"{entry['name']} levies an individual income tax."
    )
    payload["must_check"] = features
    payload["verify_with"] = entry.get("source_url")
    return payload


def _find_code(code: str) -> str:
    table = _state_table()["jurisdictions"]
    if code and code.upper() in table:
        return code.upper()
    for key, entry in table.items():
        if entry["name"].lower() == str(code).strip().lower():
            return key
    raise KeyError(f"Unknown jurisdiction {code!r}.")


def compute(
    code: str,
    *,
    tax_year: str | int,
    filing_status: str,
    agi: Any,
    wage_income: Any = None,
    interest_income: Any = 0,
    dividend_income: Any = 0,
) -> dict[str, Any]:
    """State return attempt. Returns a figure, or a refusal explaining why not."""
    code_key = _find_code(code)
    entry = jurisdiction(code_key)
    year = str(tax_year)

    base = {
        "jurisdiction": code_key,
        "name": entry["name"],
        "tax_year": year,
        "filing_status": filing_status,
        "type": entry["type"],
        "source_url": entry.get("source_url"),
    }

    # ---- genuinely zero-tax states -------------------------------------
    if code_key in _WAGE_INCOME_TAX_FREE:
        base.update({
            "state_tax": 0.0,
            "may_prepare_return": True,
            "explanation": _WAGE_INCOME_TAX_FREE[code_key],
            "caveats": [
                "Municipal or county income taxes may still apply and are NOT modeled.",
                "This covers the STATE return only. It is not a clearance for local tax.",
            ],
        })
        return base

    # ---- NH / TN: tax wages no, but tax investment income --------------
    if code_key in _INTEREST_DIVIDEND_ONLY:
        investment = money(interest_income) + money(dividend_income)
        base.update({
            "state_tax": None,
            "may_prepare_return": False,
            "refusal": "PARTIAL TAX BASE — requires a jurisdiction-specific computation",
            "explanation": _INTEREST_DIVIDEND_ONLY[code_key],
            "inputs_required": {
                "interest_income": float(money(interest_income)),
                "dividend_income": float(money(dividend_income)),
                "combined_investment_income": float(investment),
            },
            "caveats": [
                "Wage income is not taxed here, but a return may still be required.",
                "The rate and any legislative changes must be confirmed with the DOR.",
            ],
        })
        return base

    # ---- data-complete income-tax states (if a maintainer enables one) --
    per_year = entry.get("brackets", {}).get(year)
    if entry.get("data_complete") and per_year:
        from .federal import bracket_tax  # reuse verified bracket walker

        taxable = max(Decimal(0), money(agi))
        owed = money(bracket_tax(taxable, per_year))
        base.update({
            "state_tax": float(owed),
            "may_prepare_return": True,
            "explanation": f"Computed from {entry['name']} brackets loaded for TY{year}.",
            "must_check": entry.get("special_features", []),
        })
        return base

    # ---- everything else: refuse, with the checklist --------------------
    features = entry.get("special_features", [])
    top = entry.get("top_rate")
    base.update({
        "state_tax": None,
        "may_prepare_return": False,
        "refusal": "NOT COMPUTABLE — verified bracket data not loaded for this jurisdiction",
        "explanation": (
            f"{entry['name']} levies an individual income tax and this build does not "
            f"carry verified per-year brackets for it, so no tax figure is returned. "
            + (f"Recorded top marginal rate (orientation only): {top * 100:.2f}%. "
               if top else "")
            + f"Confirm the current rate with {entry.get('source_url') or 'the state DOR'}."
        ),
        "must_check": features,
        "how_to_enable": (
            f"Populate ha/rules/states.json -> jurisdictions.{code_key}.brackets.{year} "
            f"from the {entry['name']} DOR return instructions, then set "
            f"data_complete=true."
        ),
    })
    return base
