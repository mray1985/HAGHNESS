"""HA Tax Software — embedded local assistant.

Deterministic retrieval over ha/ai/kb.py, plus live lookups into the engines so
the assistant can answer "what are MY brackets" with the caller's own data.

Design constraints, all deliberate:

* No network. No model weights. No external API. Nothing to download.
* No generation. Every sentence emitted exists verbatim in a card or is
  assembled from a field of the rule files. A model that could hallucinate a
  dollar figure is worse than no model at all in a tax tool.
* Every answer carries the citation and verified flag of the card it came from.

Retrieval is Okapi BM25 over card keywords and question variants, which is
enough to route a tax question to the right card without an embedding model.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from ..rules import FILING_STATUS_LABELS, available_years, jurisdiction
from ..engine import federal as fed
from ..engine import states as st
from .kb import CARDS

_TOKEN = re.compile(r"[a-z0-9]+")

_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "does", "for",
    "from", "how", "i", "if", "in", "is", "it", "me", "my", "of", "on", "or",
    "so", "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "to", "was", "what", "when", "where", "which", "who", "why", "will",
    "with", "you", "your", "can", "get", "would", "should", "about", "much",
    "many", "any", "not", "have", "has", "was", "were", "been", "than", "also",
}

BM25_K1 = 1.5
BM25_B = 0.75


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def _card_terms(card: dict) -> list[str]:
    """Weighted corpus representation of a card: keywords triple-counted."""
    terms: list[str] = []
    terms += card.get("keywords", []) * 3
    terms += card.get("questions", []) * 2
    terms += [card.get("topic", "")] * 2
    terms += card.get("answer", "").split()
    out: list[str] = []
    for term in terms:
        out += tokenize(term)
    return out


_CORPUS: list[list[str]] = [_card_terms(c) for c in CARDS]
_DF: Counter[str] = Counter()
for _terms in _CORPUS:
    _DF.update(set(_terms))
_AVG_LEN = sum(len(t) for t in _CORPUS) / max(1, len(_CORPUS))
_N = len(_CORPUS)


def _bm25(query_terms: list[str], doc_terms: list[str]) -> float:
    if not doc_terms:
        return 0.0
    freq = Counter(doc_terms)
    length = len(doc_terms)
    score = 0.0
    for term in query_terms:
        if term not in freq:
            continue
        n = _DF[term]
        idf = math.log(1 + (_N - n + 0.5) / (n + 0.5))
        tf = freq[term]
        denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * length / _AVG_LEN)
        score += idf * (tf * (BM25_K1 + 1)) / denom
    return score


def search(query: str, top: int = 3) -> list[tuple[dict, float]]:
    terms = tokenize(query)
    if not terms:
        return []
    scored = [
        (card, _bm25(terms, doc))
        for card, doc in zip(CARDS, _CORPUS)
    ]
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    # Exact question-string match always wins its topic outright.
    needle = " ".join(terms)
    for card, _ in scored:
        for variant in card.get("questions", []):
            if needle and needle in " ".join(tokenize(variant)):
                return [(card, 1000.0)] + [p for p in scored if p[0] is not card][:top - 1]
    return scored[:top]


# --------------------------------------------------------------------------
# live engine intents
# --------------------------------------------------------------------------

_YEAR_HINT = re.compile(r"\b(20\d\d)\b")

_STATUS_HINT = {
    "single": "single", "married jointly": "mfj", "mfj": "mfj",
    "jointly": "mfj", "married separately": "mfs", "mfs": "mfs",
    "head of household": "hoh", "hoh": "hoh", "widow": "qss", "qss": "qss",
    "surviving spouse": "qss",
}

_STATE_HINT = re.compile(r"\b([A-Z]{2})\b")

#: Two-letter codes that are also common English words. Matching these
#: case-insensitively turns "show ME the brackets" into a Maine tax question.
_AMBIGUOUS_CODES = {"ME", "IN", "OR", "AT", "IT", "OK", "HI", "SO", "NO", "IF", "ON", "TO", "LA"}


def _detect_year(text: str, default: str) -> str:
    years = available_years()
    found = _YEAR_HINT.search(text)
    if found and found.group(1) in years:
        return found.group(1)
    return default if default in years else "2025"


def _detect_status(text: str) -> str | None:
    lowered = text.lower()
    for needle, code in _STATUS_HINT.items():
        if needle in lowered:
            return code
    return None


def _detect_state(text: str) -> str | None:
    """Resolve a jurisdiction from a full name or a two-letter code.

    Full names are matched case-insensitively. Two-letter codes must appear
    UPPERCASE in the original text, and ambiguous codes are rejected outright
    unless the user spelled out the name. Otherwise "does ME have state tax"
    routes to Maine because 'me' is a pronoun.
    """
    table = st.list_jurisdictions()
    lowered = text.lower()

    for row in table:
        if row["name"].lower() in lowered:
            return row["code"]

    for match in _STATE_HINT.findall(text):
        if match in _AMBIGUOUS_CODES:
            continue
        if any(row["code"] == match for row in table):
            return match
    return None


# --------------------------------------------------------------------------

_OWE_RE = re.compile(r"\b(how\s+much|what)\b.*\b(i|my|me)\b.*\b(owe|pay|owed)\b", re.I)


class Assistant:
    """Rule-grounded assistant. Stateless between calls; caller owns history."""

    def __init__(self) -> None:
        self.name = "HA-RuleBot"
        self.version = "0.1.0"

    # -- public ---------------------------------------------------------
    def ask(
        self,
        question: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = context or {}
        text = (question or "").strip()
        if not text:
            return self._empty()

        year = _detect_year(text, str(ctx.get("tax_year", "2025")))
        status = _detect_status(text) or ctx.get("filing_status") or "single"
        lowered = text.lower()

        # Intent 1 — the caller wants their own numbers.
        if self._wants_personal(lowered):
            return self._personal(text, year, status, ctx)

        # Intent 2 — a specific jurisdiction.
        state_code = _detect_state(text)
        if state_code and any(
            k in lowered for k in ("tax", "rate", "bracket", "deduct", "owe", "state", "return")
        ):
            return self._state(text, state_code, year)

        # Intent 3 — bracket table.
        if "bracket" in lowered and ("my" in lowered or "show" in lowered or "what are" in lowered):
            return self._brackets(year, status)

        # Intent 4 — knowledge card retrieval.
        hits = search(text, top=2)
        if hits:
            best, score = hits[0]
            second = hits[1][1] if len(hits) > 1 else 0.0
            margin = score - second
            return self._card_answer(best, year, status, margin, hits)

        return self._fallback(year, status)

    # -- intents --------------------------------------------------------
    def _wants_personal(self, text: str) -> bool:
        if _OWE_RE.search(text):
            return True
        return any(k in text for k in (
            "my tax", "my brackets", "my return", "compute", "calculate my",
            "my credit", "my eitc", "my ctc",
        ))

    def _personal(self, text: str, year: str, status: str, ctx: dict) -> dict:
        agi = ctx.get("agi")
        if agi in (None, "", 0):
            return {
                "answer": (
                    "I can compute that, but I need your AGI - I deliberately do not derive "
                    "it, because above-the-line adjustments are where returns go wrong.\n\n"
                    "Set AGI in the Return Calculator and ask me again. I will also need the "
                    "tax year, filing status, number of qualifying children, and any net "
                    "capital gain."
                ),
                "cards": [],
                "citations": [],
                "needs_input": ["agi"],
                "confidence": "high",
            }

        result = fed.compute(
            year,
            status,
            agi,
            net_capital_gain=ctx.get("net_capital_gain", 0),
            qualifying_children=ctx.get("qualifying_children", 0),
            investment_income=ctx.get("investment_income", 0),
            earned_income=ctx.get("earned_income"),
        )
        lines = result["lines"]
        credits = result["credits"]
        summary = (
            f"TY{year}, {FILING_STATUS_LABELS[status]}, AGI ${lines['taxable_income'] + lines['standard_deduction']:,.0f}.\n\n"
            f"Standard deduction:  ${lines['standard_deduction']:,.2f}\n"
            f"Taxable income:      ${lines['taxable_income']:,.2f}\n"
            f"Tax before credits:  ${lines['tax_before_credits']:,.2f}\n"
            f"Child tax credit:   ${credits['child_tax_credit']['used_against_tax']:,.2f}"
            f"  (computed ${credits['child_tax_credit']['base']:,.2f}, phase-out "
            f"${credits['child_tax_credit']['phaseout']:,.2f})\n"
            f"EITC:                ${credits['eitc']['credit']:,.2f}\n"
            f"Tax after credits:   ${result['result']['tax_after_credits']:,.2f}\n"
            f"Marginal rate:       {lines['marginal_rate_on_last_dollar'] * 100:.2f}%"
        )
        if not result["verification"]["year_final"]:
            summary += (
                f"\n\n!! TY{year} figures are PROJECTIONS, not final law. "
                "Planning estimate only."
            )
        if not result["verification"]["human_checked"]:
            summary += (
                f"\n!! TY{year} figures have NOT been checked against "
                f"{result['citation']}. Do not use this on a return until a "
                "human records the check in ha/rules/verification.json."
            )
        summary += (
            "\n\nThis is 1040 core only. It does not include Schedules 1-4, itemized "
            "deductions, AMT, or any state or local tax."
        )
        return {
            "answer": summary,
            "cards": [],
            "citations": [result["citation"]],
            "computed": result,
            "confidence": "high",
        }

    def _brackets(self, year: str, status: str) -> dict:
        table = fed.explain_brackets(year, status)
        lines = [
            f"TY{year} federal brackets — {FILING_STATUS_LABELS[status]}",
            f"Standard deduction: ${table['standard_deduction']:,.0f}",
            "",
        ]
        for row in table["brackets"]:
            span = f"${row['from']:,.0f}"
            if row["to"] is None:
                span += " and above"
            else:
                span += f" to ${row['to'] - 1:,.0f}"
            lines.append(f"  {row['rate_label']:>6}   {span}")
        lines.append("")
        lines.append(f"Source: {table['citation']}")
        if table["year_status"] != "final":
            lines.append("")
            lines.append("!! PROJECTED FIGURES - not final law.")
        return {
            "answer": "\n".join(lines),
            "cards": [],
            "citations": [table["citation"]],
            "table": table,
            "confidence": "high",
        }

    def _state(self, text: str, code: str, year: str) -> dict:
        info = st.detail(code)
        if info["computable"]:
            body = (
                f"{info['name']}: {info['explanation']}\n\nState income tax: $0.00"
            )
            if info.get("caveats"):
                body += "\n\n" + "\n".join(f"- {c}" for c in info["caveats"])
            return {
                "answer": body,
                "cards": [],
                "citations": [info.get("source_url") or "State DOR"],
                "state": info,
                "confidence": "high",
            }

        body = [f"{info['name']} — I will not give you a number for this one.", "", info["explanation"], ""]
        if info.get("must_check"):
            body.append("What a preparer must check:")
            body += [f"  - {f}" for f in info["must_check"]]
            body.append("")
        body.append(f"Verify at: {info.get('verify_with') or info.get('source_url')}")
        return {
            "answer": "\n".join(body),
            "cards": ["states.why_no_numbers"],
            "citations": [info.get("source_url") or "State DOR"],
            "state": info,
            "refused": info.get("refusal"),
            "confidence": "high",
        }

    def _card_answer(
        self, card: dict, year: str, status: str, margin: float, hits: list
    ) -> dict:
        body = card["answer"]
        if not card.get("verified", False):
            body += (
                "\n\n[Figures in this answer are flagged for confirmation against the "
                "cited authority before use on a return.]"
            )
        body += f"\n\nSource: {card['citation']}"
        return {
            "answer": body,
            "cards": [card["id"]],
            "citations": [card["citation"]],
            "verified": card.get("verified", False),
            "confidence": "high" if margin > 1.0 else "medium",
            "alternatives": [c["id"] for c, _ in hits[1:]],
        }

    def _fallback(self, year: str, status: str) -> dict:
        return {
            "answer": (
                "I do not have a rule card for that, and I will not improvise a tax answer.\n\n"
                "I cover: the standard deduction, brackets and marginal vs effective rates, "
                "the child tax credit, the EITC, capital gains and netting, filing deadlines "
                "and extensions, self-employment tax, 1099 vs W-2, AMT, HSAs, the deduction "
                "ordering question, record retention, audit triggers, and all 50 state tax "
                "structures.\n\n"
                "For anything outside that, go to the primary source - the IRS instructions "
                "for the form, or the state DOR - rather than trusting a guess from any tool, "
                "including me."
            ),
            "cards": [],
            "citations": [],
            "confidence": "low",
            "uncovered": True,
        }

    def _empty(self) -> dict:
        return {
            "answer": "Ask me about a tax rule and I will cite the authority.",
            "cards": [], "citations": [], "confidence": "high",
        }
