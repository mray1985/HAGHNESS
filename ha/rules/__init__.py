"""HA Tax Software — rule loading and provenance.

All statutory figures live in JSON under this package. Nothing in the code
hardcodes a dollar amount. Every rule block carries its own verification
metadata so the engine can refuse to produce a return figure it cannot
defend.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_DIR = Path(__file__).resolve().parent

FILING_STATUSES = ("single", "mfj", "mfs", "hoh", "qss")

FILING_STATUS_LABELS = {
    "single": "Single",
    "mfj": "Married Filing Jointly",
    "mfs": "Married Filing Separately",
    "hoh": "Head of Household",
    "qss": "Qualifying Surviving Spouse",
}

#: Statuses whose phase-out thresholds are expressed on a joint basis.
_JOINT_BASIS = ("mfj", "qss")

CENTS = Decimal("0.01")


def D(value: Any) -> Decimal:
    """Coerce to Decimal via str so binary float error never enters the math."""
    if value is None:
        return Decimal(0)
    if isinstance(value,bool) or not isinstance(value,(Decimal,str,int,float)):
        raise ValueError('A finite numeric amount is required')
    try:
        amount=Decimal(str(value))
        if not amount.is_finite():raise ValueError('A finite numeric amount is required')
        return amount
    except InvalidOperation as error:
        raise ValueError('A finite numeric amount is required') from error


def money(value: Any) -> Decimal:
    """Round to cents, half-up, the way the IRS rounds."""
    return D(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def fmt(amount: Any) -> str:
    return f"${money(amount):,.2f}"


@lru_cache(maxsize=None)
def _read(name: str) -> dict:
    path = RULES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def _merge_verification() -> dict:
    """Overlay the human verification ledger onto the rule data.

    The 'verified' flag in the rule files is authored by whoever wrote them and
    starts false. The ledger in verification.json is the only input that can
    raise it, and only when a named person recorded a check. That ordering is
    deliberate: a rule file can never self-certify.
    """
    rules = _read("federal")
    ledger = _read("verification").get("federal", {})
    for year, block in rules["years"].items():
        record = ledger.get(year, {})
        block["verified"] = bool(record.get("verified", False))
        block["verification"] = {
            "checked_by": record.get("checked_by"),
            "checked_on": record.get("checked_on"),
            "against": record.get("against"),
            "items_to_confirm": record.get("items_to_confirm", []),
            "note": record.get("note"),
        }
    return rules


@lru_cache(maxsize=None)
def _raw_federal() -> dict:
    return _read("federal")


def federal() -> dict:
    return _merge_verification()


def states() -> dict:
    return _read("states")


def year_block(tax_year: str | int) -> dict:
    """Return the rule block for a tax year, or raise a clear error."""
    key = str(tax_year)
    block = federal()["years"].get(key)
    if block is None:
        raise KeyError(
            f"No rule data for tax year {key}. Available: "
            + ", ".join(sorted(federal()["years"]))
        )
    return block


def available_years() -> list[str]:
    return sorted(federal()["years"])


def verification_ledger() -> dict:
    """The human-check record, for display in the UI."""
    return _read("verification")


def normalize_status(status: str) -> str:
    key = (status or "").strip().lower()
    aliases = {
        "s": "single",
        "single": "single",
        "mfj": "mfj",
        "married filing jointly": "mfj",
        "j": "mfj",
        "mfs": "mfs",
        "married filing separately": "mfs",
        "hoh": "hoh",
        "head of household": "hoh",
        "h": "hoh",
        "qss": "qss",
        "qualifying widow(er)": "qss",
        "qualifying surviving spouse": "qss",
        "w": "qss",
    }
    if key not in aliases:
        raise ValueError(
            f"Unknown filing status {status!r}. Expected one of: "
            + ", ".join(FILING_STATUSES)
        )
    return aliases[key]


def is_joint(status: str) -> bool:
    return normalize_status(status) in _JOINT_BASIS


def jurisdiction(code: str) -> dict:
    """Look up a state/DC entry. Accepts 'NY' or 'ny' or 'New York'."""
    table = states()["jurisdictions"]
    if code and code.upper() in table:
        return table[code.upper()]
    for entry in table.values():
        if entry["name"].lower() == str(code).strip().lower():
            return entry
    raise KeyError(
        f"Unknown jurisdiction {code!r}. This build covers 50 states + DC only. "
        "Local municipal taxes are not modeled."
    )


def unverified_items(year_block: dict) -> list[str]:
    """Every sub-rule in a year block that is not human-verified.

    The year block itself is included, so a caller can never see an empty list
    and infer the year is fully checked unless a human actually checked it.
    """
    found: list[str] = []
    if not year_block.get("verified", False):
        found.append("_year_block")
    for key, value in year_block.items():
        if isinstance(value, dict) and value.get("verified") is False:
            found.append(key)
    return sorted(found)
