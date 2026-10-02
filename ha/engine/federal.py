"""HA Tax Software — federal individual income tax engine.

Scope: Form 1040 core mechanics for TY2024/2025/2026 — standard deduction,
ordinary-income bracket tax, preferential capital-gain stacking, the child
tax credit, and the earned income tax credit.

Out of scope, deliberately. These are the parts a preparer must not get from a
calculator, and the engine will not fake them:

  * itemized deductions and the itemize-or-standard comparison
  * Schedule 1 through Schedule 4 adders (self-employment, retirement
    contributions, HSA deductions, alimony, IRA deductions, student loan
    interest, other-than-primary-residence mortgage interest phase-out)
  * above-the-line adjustments to AGI
  * the ACTC+EITC special rule for tax years 2021-2025
  * AMT (Form 6251)
  * net investment income tax
  * phase-outs of itemized deductions tied to MAGI
  * qualified business income (Section 199A)
  * excess advance premium tax credit repayment (Form 8962)
  * any state or local tax

AGI is therefore taken as an INPUT, not computed. The engine is honest about
that rather than silently returning a plausible-looking wrong total.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..rules import (
    D,
    fmt,
    is_joint,
    money,
    normalize_status,
    unverified_items,
    year_block,
)

INF = Decimal("Infinity")


# --------------------------------------------------------------------------
# bracket mechanics
# --------------------------------------------------------------------------

def _ceiling(upper: Any) -> Decimal:
    return INF if upper is None else D(upper)


def bracket_tax(taxable_income: Decimal, brackets: list[list[Any]]) -> Decimal:
    """Marginal tax on taxable income. Bracket bounds are lower-exclusive.

    Each row is [lower, upper, rate]. Rows share boundary values, so the amount
    in band i is (min(income, upper_i) - lower_i) and no income is taxed twice.
    """
    total = Decimal(0)
    remaining = taxable_income
    if remaining <= 0:
        return total
    for lower, upper, rate in brackets:
        low = D(lower)
        if remaining <= low:
            break
        span = min(remaining, _ceiling(upper)) - low
        if span > 0:
            total += span * D(rate)
    return total


def marginal_rate(taxable_income: Decimal, brackets: list[list[Any]]) -> Decimal:
    if taxable_income <= 0:
        return Decimal(0)
    for lower, upper, rate in brackets:
        if taxable_income <= _ceiling(upper):
            return D(rate)
    return Decimal(0)


def _band(rows: list[list[Any]], income: Decimal, rate: Decimal) -> Decimal:
    """Portion of `income` falling in bands taxed at exactly `rate`."""
    total = Decimal(0)
    remaining = income
    if remaining <= 0:
        return total
    for lower, upper, band_rate in rows:
        low = D(lower)
        if remaining <= low:
            break
        if D(band_rate) == rate:
            span = min(remaining, _ceiling(upper)) - low
            if span > 0:
                total += span
    return total


# --------------------------------------------------------------------------
# preferential capital gains
# --------------------------------------------------------------------------

def capital_gains_tax(
    net_capital_gain: Decimal,
    ordinary_income: Decimal,
    year: dict,
    status: str,
) -> dict[str, Any]:
    """Tax on net capital gain using the Schedule D computation.

    Correct mechanics, stated plainly because the shortcut is a common bug.

    The preferential bands are measured against TOTAL taxable income. The 0%
    band shelters however much of the gain sits below the 0% ceiling, and that
    portion is taxed at ZERO - it is NOT charged at the ordinary rate. That is
    the entire purpose of the 0% bracket: it stops a filer with a modest gain
    from being pushed into a higher ordinary bracket by the gain itself.

    So the total is:

        bracket_tax(ordinary_income) + 15% band + 20% band

    with no ordinary-rate tax layered onto the gain. Charging the 0% band at
    the ordinary rate would make the 0% bracket meaningless.

    `ordinary_income` MUST be taxable_income minus net_capital_gain.
    """
    brackets = year["brackets"][status]
    if net_capital_gain <= 0:
        # No preferential stacking: the whole of taxable income is ordinary.
        ordinary = money(bracket_tax(ordinary_income, brackets))
        return {
            "tax": ordinary,
            "zero_rate_amount": Decimal(0),
            "fifteen_rate_amount": Decimal(0),
            "twenty_rate_amount": Decimal(0),
            "tax_if_all_ordinary": Decimal(0),
            "ordinary_tax_on_non_gain": ordinary,
        }

    rows = year["capital_gains_rates"][status]
    zero_ceiling = D(rows[0][1])
    fifteen_ceiling = D(rows[1][1])

    # Gain sheltered by the 0% band: limited by headroom above ordinary income.
    zero_band = min(net_capital_gain, max(Decimal(0), zero_ceiling - ordinary_income))
    # Gain landing in the 15% band.
    fifteen_room = max(Decimal(0), fifteen_ceiling - ordinary_income - zero_band)
    fifteen_band = min(max(Decimal(0), net_capital_gain - zero_band), fifteen_room)
    twenty_band = max(Decimal(0), net_capital_gain - zero_band - fifteen_band)

    tax_on_ordinary = bracket_tax(ordinary_income, brackets)
    gain_tax = (
        tax_on_ordinary
        + fifteen_band * D("0.15")
        + twenty_band * D("0.20")
    )

    return {
        "tax": money(gain_tax),
        "zero_rate_amount": money(zero_band),
        "fifteen_rate_amount": money(fifteen_band),
        "twenty_rate_amount": money(twenty_band),
        "tax_if_all_ordinary": money(
            bracket_tax(ordinary_income + net_capital_gain, brackets)
        ),
        "ordinary_tax_on_non_gain": money(tax_on_ordinary),
    }


# --------------------------------------------------------------------------
# child tax credit
# --------------------------------------------------------------------------

def child_tax_credit(
    qualifying_children: int, modified_agi: Decimal, year: dict, status: str
) -> dict[str, Any]:
    """CTC with the $50-per-$1,000 MAGI phase-out (Stat. 24(h)(2))."""
    rule = year["child_tax_credit"]
    per_child = D(rule["amount_per_child"])
    base = per_child * Decimal(max(0, qualifying_children))
    if base == 0:
        return {
            "base": Decimal(0), "phaseout": Decimal(0), "credit": Decimal(0),
            "per_child": per_child, "children": 0, "fully_phased_out": False,
        }

    threshold = D(rule["phaseout_magi_mfj"] if is_joint(status) else rule["phaseout_magi_single"])
    increment = D(rule["phaseout_increment"])
    reduction = D(rule["phaseout_reduction"])

    excess = max(Decimal(0), modified_agi - threshold)
    # "$50 for each $1,000, or fraction" => round the number of increments up.
    increments = (excess / increment).to_integral_value(rounding="ROUND_CEILING")
    phaseout = increments * reduction
    credit = max(Decimal(0), base - phaseout)

    return {
        "base": money(base),
        "phaseout": money(phaseout),
        "credit": money(credit),
        "per_child": per_child,
        "children": qualifying_children,
        "threshold": threshold,
        "fully_phased_out": credit == 0 and excess > 0,
    }


# --------------------------------------------------------------------------
# earned income tax credit
# --------------------------------------------------------------------------

def eitc(
    earned_income: Decimal,
    agi_without_eitc: Decimal,
    qualifying_children: int,
    investment_income: Decimal,
    year: dict,
    status: str,
) -> dict[str, Any]:
    """EITC. Both earned income and AGI are phased out and the WORSE result wins.

    IRC 32(a)(2) requires the credit to be recomputed with each of earned
    income and AGI-in-exclusion-of-the-credit, then the smaller credit is used.
    Using only earned income is the classic bug that overstates the credit.
    """
    rule = year["eitc"]
    children = max(0, min(3, qualifying_children))
    key = str(children)
    basis = "mfj" if is_joint(status) else "single"

    max_credit = D(rule["max_credit"][key])
    phaseout_rate = D(rule["phaseout_rate"][key])
    start = D(rule["phaseout_start_income"][basis][key])
    end = D(rule["phaseout_end_income"][basis][key])
    inv_limit = D(rule["investment_income_limit"][basis])
    ceiling = D(rule["earned_income_and_agi_ceiling"][basis][key])

    if investment_income > inv_limit:
        return {
            "credit": Decimal(0), "disqualified": "investment income",
            "investment_income": investment_income,
            "investment_income_limit": inv_limit,
            "max_credit": max_credit, "children": children,
            "phaseout_start": start, "phaseout_end": end,
        }

    def phase(base: Decimal) -> Decimal:
        if base > end:
            return Decimal(0)
        if base <= start:
            return max_credit
        return max(Decimal(0), max_credit - (base - start) * phaseout_rate)

    credit_ei = phase(earned_income)
    credit_agi = phase(agi_without_eitc)
    credit = min(credit_ei, credit_agi)
    # IRC 32 requires earned income. Eligibility/phase-in remain incomplete.
    if earned_income <= 0:
        credit = credit_ei = Decimal(0)

    # Hard ceiling: no credit at all if either measure exceeds the limit.
    if earned_income > ceiling or agi_without_eitc > ceiling:
        credit = Decimal(0)

    return {
        "credit": money(credit),
        "credit_from_earned_income": money(credit_ei),
        "credit_from_agi": money(credit_agi),
        "binding_measure": "earned_income" if credit_ei <= credit_agi else "agi",
        "disqualified": None,
        "max_credit": max_credit,
        "phaseout_rate": phaseout_rate,
        "phaseout_start": start,
        "phaseout_end": end,
        "children": children,
        "qualifying_children": qualifying_children,
    }


# --------------------------------------------------------------------------
# return assembly
# --------------------------------------------------------------------------

def compute(
    tax_year: str | int,
    filing_status: str,
    agi: Any,
    *,
    net_capital_gain: Any = 0,
    qualifying_children: int = 0,
    investment_income: Any = 0,
    earned_income: Any = None,
) -> dict[str, Any]:
    """Build a Form 1040 core return. AGI is an input, not a computation.

    `earned_income` defaults to AGI. That default is convenient and it is
    usually right, but it disables the EITC's second phase-out test, since
    earned income and AGI then always tie. Supply it separately whenever the two
    actually differ - a large capital gain, taxable Social Security, or an
    unusual deduction.
    """
    year = year_block(tax_year)
    status = normalize_status(filing_status)

    agi_d = money(agi)
    if agi_d < 0:
        raise ValueError("AGI cannot be negative in this engine.")

    gain_d = money(net_capital_gain)
    if gain_d < 0:
        raise ValueError('Capital losses require a netting/AGI workflow not supported by this engine.')
    standard_deduction = D(year["standard_deduction"][status])
    taxable_income = max(Decimal(0), agi_d - standard_deduction)
    brackets = year["brackets"][status]

    # The gain is carved OUT of taxable income; the rest is ordinary.
    gain_applicable = min(gain_d, taxable_income)
    ordinary_income = taxable_income - gain_applicable

    cap = capital_gains_tax(gain_applicable, ordinary_income, year, status)
    total_tax = cap["tax"]
    ordinary_only = cap["ordinary_tax_on_non_gain"]
    has_capgain = gain_applicable > 0

    ctc = child_tax_credit(qualifying_children, agi_d, year, status)
    earned_d = money(earned_income) if earned_income is not None else agi_d
    eitc_result = eitc(
        earned_d,
        agi_d,
        qualifying_children,
        money(investment_income),
        year,
        status,
    )

    nonrefundable = min(ctc["credit"], total_tax)
    ctc_unused = ctc["credit"] - nonrefundable
    refundable = eitc_result["credit"]

    tax_after_credits = max(Decimal(0), total_tax - nonrefundable - refundable)
    overpaid = max(Decimal(0), nonrefundable + refundable - total_tax)

    # ---- verification report -------------------------------------------
    # Two independent conditions. 'final' is a statement about the tax year.
    # 'verified' is a statement about whether a named human checked these
    # digits against the cited authority. Both are required, and the second
    # is false for every year until someone records a check.
    year_final = year.get("status") == "final"
    unverified = unverified_items(year)
    human_checked = year.get("verified", False)

    blockers: list[str] = []
    if not year_final:
        blockers.append(
            f"TY{tax_year} rule data is a projection, not final law. "
            "No return may be prepared from it."
        )
    if not human_checked:
        record = year.get("verification", {})
        against = record.get("against") or year.get("citation")
        blockers.append(
            f"TY{tax_year} figures have not been checked against a primary source. "
            f"They were transcribed without reading {against}. Confirm the digits and "
            f"record the check in ha/rules/verification.json."
        )
    for item in unverified:
        if item == "_year_block":
            continue
        blockers.append(f"Sub-rule not human-verified: {item}")

    result = {
        "tax_year": str(tax_year),
        "year_status": year.get("status"),
        "citation": year.get("citation"),
        "filing_status": status,
        "inputs": {
            "agi": float(agi_d),
            "earned_income": float(earned_d),
            "net_capital_gain": float(gain_d),
            "qualifying_children": qualifying_children,
            "investment_income": float(money(investment_income)),
        },
        "lines": {
            "standard_deduction": float(standard_deduction),
            "taxable_income": float(taxable_income),
            "tax_before_credits": float(total_tax),
            "ordinary_taxable_income": float(ordinary_income),
            "ordinary_tax_on_non_gain": float(ordinary_only),
            "capital_gains_tax": float(cap["tax"]) if has_capgain else 0.0,
            "marginal_rate_on_last_dollar": float(marginal_rate(taxable_income, brackets)),
            "marginal_bracket_ceiling": float(_ceiling(
                next(r[1] for r in brackets if taxable_income <= _ceiling(r[1]))
            )) if taxable_income > 0 else 0.0,
        },
        "credits": {
            "child_tax_credit": {
                "base": float(ctc["base"]),
                "phaseout": float(ctc["phaseout"]),
                "used_against_tax": float(nonrefundable),
                "unused_overpayment": float(ctc_unused),
                "per_child": float(ctc["per_child"]),
                "children": ctc["children"],
                "fully_phased_out": ctc["fully_phased_out"],
            },
            "eitc": {
                "credit": float(eitc_result["credit"]),
                "max_credit": float(eitc_result["max_credit"]),
                "children": eitc_result["children"],
                "binding_measure": eitc_result.get("binding_measure"),
                "phaseout_start": float(eitc_result["phaseout_start"]),
                "phaseout_end": float(eitc_result["phaseout_end"]),
                "disqualified": eitc_result.get("disqualified"),
            },
        },
        "capital_gains_detail": {
            "net_capital_gain": float(gain_d),
            "zero_rate_amount": float(cap["zero_rate_amount"]),
            "fifteen_rate_amount": float(cap["fifteen_rate_amount"]),
            "twenty_rate_amount": float(cap["twenty_rate_amount"]),
            "tax_if_all_ordinary": float(cap["tax_if_all_ordinary"]),
        },
        "result": {
            "tax_after_credits": float(tax_after_credits),
            "total_paid_estimate": float(max(Decimal(0), tax_after_credits)),
            "refund_estimate": float(overpaid),
        },
        "verification": {
            "year_final": year_final,
            "human_checked": human_checked,
            "checked_by": year.get("verification", {}).get("checked_by"),
            "checked_on": year.get("verification", {}).get("checked_on"),
            "against": year.get("citation"),
            "unverified_items": unverified,
            "blockers": blockers,
            "may_prepare_return": year_final and human_checked and not blockers,
            "scope": "1040 core only. AGI is caller-supplied. See module docstring.",
        },
    }
    return result


def explain_brackets(tax_year: str | int, filing_status: str) -> dict[str, Any]:
    """Human-readable bracket table plus the effective/marginal read-out."""
    year = year_block(tax_year)
    status = normalize_status(filing_status)
    brackets = year["brackets"][status]
    table = []
    for index, (low, up, rate) in enumerate(brackets):
        table.append({
            "band": index + 1,
            "from": float(D(low)),
            "to": None if up is None else float(D(up)),
            "to_label": "and above" if up is None else f"{fmt(D(up))} and below",
            "rate": float(D(rate)),
            "rate_label": f"{float(D(rate)) * 100:.2f}%".replace(".00%", "%"),
        })
    return {
        "tax_year": str(tax_year),
        "citation": year.get("citation"),
        "year_status": year.get("status"),
        "filing_status": status,
        "standard_deduction": float(D(year["standard_deduction"][status])),
        "brackets": table,
        "unverified_items": unverified_items(year),
    }
