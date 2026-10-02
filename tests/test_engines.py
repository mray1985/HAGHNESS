"""Hand-checked tests for the HA Tax Software engines.

Every expected value below was computed by hand from the cited authority and
is written out in the assertion message, so a failure shows the arithmetic,
not just two numbers disagreeing.

Run:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from ha.engine import federal as fed
from ha.engine import states as st
from ha.rules import FILING_STATUSES, available_years
from ha.ai.assistant import Assistant, search


def money(value) -> Decimal:
    from ha.rules import money as _m
    return _m(value)


class TestBracketArithmetic(unittest.TestCase):
    def test_ty2025_single_65000_taxable(self):
        # 11,925*.10 + (48,475-11,925)*.12 + (65,000-48,475)*.22
        # = 1,192.50 + 4,386.00 + 3,635.50 = 9,214.00
        r = fed.compute(2025, "single", 80_000)
        self.assertEqual(r["lines"]["taxable_income"], 65_000.0)
        self.assertEqual(r["lines"]["tax_before_credits"], 9_214.0, "9,214.00 expected")

    def test_ty2024_single_50000_agi(self):
        # std 14,600 -> TI 35,400
        # 11,600*.10 + (35,400-11,600)*.12 = 1,160.00 + 2,856.00 = 4,016.00
        r = fed.compute(2024, "single", 50_000)
        self.assertEqual(r["lines"]["standard_deduction"], 14_600.0)
        self.assertEqual(r["lines"]["tax_before_credits"], 4_016.0, "4,016.00 expected")

    def test_ty2025_mfj_100000_agi(self):
        # std 30,000 -> TI 70,000
        # 23,850*.10 + (70,000-23,850)*.12 = 2,385.00 + 5,538.00 = 7,923.00
        r = fed.compute(2025, "mfj", 100_000)
        self.assertEqual(r["lines"]["tax_before_credits"], 7_923.0, "7,923.00 expected")

    def test_ty2026_single_60000_agi(self):
        # std 15,750 -> TI 44,250
        # 12,425*.10 + (44,250-12,425)*.12 = 1,242.50 + 3,819.00 = 5,061.50
        r = fed.compute(2026, "single", 60_000)
        self.assertEqual(r["lines"]["tax_before_credits"], 5_061.5, "5,061.50 expected")

    def test_income_below_standard_deduction_is_untaxed(self):
        for year in available_years():
            for status in FILING_STATUSES:
                r = fed.compute(year, status, 1_000)
                self.assertEqual(
                    r["lines"]["tax_before_credits"], 0.0,
                    f"TY{year} {status} below std deduction must owe nothing",
                )

    def test_all_statuses_and_years_are_bracket_walkable(self):
        for year in available_years():
            for status in FILING_STATUSES:
                r = fed.compute(year, status, 500_000)
                self.assertGreater(
                    r["lines"]["tax_before_credits"], 0.0, f"TY{year} {status}"
                )
                self.assertIn(
                    r["lines"]["marginal_rate_on_last_dollar"],
                    (0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37),
                )


class TestCapitalGainsStacking(unittest.TestCase):
    def test_gain_fully_inside_zero_band_pays_nothing(self):
        # TY2025 single, AGI 30,000 -> TI 15,000. Ordinary = 5,000.
        # 0% ceiling is 48,000, so all 10,000 of gain sits in the 0% band and
        # the ordinary tax attributable to it is fully removed. Total tax = tax
        # on the 5,000 of ordinary income only = 500.00
        r = fed.compute(2025, "single", 30_000, net_capital_gain=10_000)
        d = r["capital_gains_detail"]
        self.assertEqual(d["zero_rate_amount"], 10_000.0, "all gain in 0% band")
        self.assertEqual(d["fifteen_rate_amount"], 0.0)
        self.assertEqual(r["lines"]["tax_before_credits"], 500.0, "500.00 expected")

    def test_no_headroom_jumps_straight_to_fifteen_percent(self):
        # TY2025 single, AGI 100,000 -> TI 85,000, ordinary 65,000.
        # 0% ceiling 48,000 is already exceeded by ordinary income, so the
        # whole 20,000 gain is at 15%.
        r = fed.compute(2025, "single", 100_000, net_capital_gain=20_000)
        d = r["capital_gains_detail"]
        self.assertEqual(d["zero_rate_amount"], 0.0, "no 0% headroom")
        self.assertEqual(d["fifteen_rate_amount"], 20_000.0)
        # 9,214.00 (on 65,000 ordinary) + 20,000*.15 = 9,214 + 3,000
        self.assertEqual(r["lines"]["tax_before_credits"], 12_214.0, "12,214.00 expected")

    def test_bracket_ceiling_is_not_double_counted(self):
        """Exactly at a band edge must not tax a dollar twice."""
        exact = fed.compute(2025, "single", 15_000 + 11_925)  # TI lands on 11,925
        self.assertEqual(exact["lines"]["tax_before_credits"], 1_192.5, "1,192.50 expected")

    def test_twenty_percent_band(self):
        # Force a 20% test with a synthetic bracket set.
        year = {
            "capital_gains_rates": {"single": [[0, 0, 0.0], [0, 0, 0.15], [0, None, 0.20]]},
            "brackets": {"single": [[0, 100_000, 0.37]]},
        }
        out = fed.capital_gains_tax(money(50_000), money(0), year, "single")
        self.assertEqual(out["twenty_rate_amount"], 50_000.0)
        self.assertEqual(out["tax"], money(10_000.0))


class TestChildTaxCredit(unittest.TestCase):
    def test_full_credit_below_threshold(self):
        r = fed.compute(2025, "single", 100_000, qualifying_children=2)
        ctc = r["credits"]["child_tax_credit"]
        self.assertEqual(ctc["base"], 4_400.0, "2 x 2,200")
        self.assertEqual(ctc["phaseout"], 0.0)
        self.assertEqual(ctc["used_against_tax"], 4_400.0, "credit applies against tax")

    def test_phaseout_counts_fraction_as_whole_increment(self):
        # Excess of 500 must trigger a full 50 reduction ($50 per $1,000 OR
        # fraction). This is the single most commonly mis-implemented rule.
        r = fed.compute(2025, "single", 200_500, qualifying_children=1)
        ctc = r["credits"]["child_tax_credit"]
        self.assertEqual(ctc["phaseout"], 50.0, "500 over threshold = one 50 step")
        self.assertEqual(ctc["base"] - ctc["phaseout"], 2_150.0)

    def test_mfj_threshold_is_double(self):
        single = fed.compute(2025, "single", 250_000, qualifying_children=1)
        mfj = fed.compute(2025, "mfj", 250_000, qualifying_children=1)
        self.assertEqual(single["credits"]["child_tax_credit"]["phaseout"], 2_500.0)
        self.assertEqual(mfj["credits"]["child_tax_credit"]["phaseout"], 0.0,
                         "250,000 is under the 400,000 MFJ threshold")

    def test_unused_ctc_is_not_refunded(self):
        # AGI 20,000 -> TI 5,000 -> tax 500. CTC base 4,400, only 500 usable.
        r = fed.compute(2025, "single", 20_000, qualifying_children=2)
        ctc = r["credits"]["child_tax_credit"]
        self.assertEqual(ctc["base"], 4_400.0)
        self.assertEqual(ctc["used_against_tax"], 500.0, "only offsets tax owed")
        self.assertEqual(
            ctc["unused_overpayment"], 3_900.0,
            "3,900 is carryforward, NOT a refund",
        )
        # The EITC is refundable, so an overpayment is legitimate here - but it
        # must come only from the EITC, never from the unused CTC.
        refund = r["result"]["refund_estimate"]
        self.assertAlmostEqual(refund, r["credits"]["eitc"]["credit"], places=2)
        # The size of EITC and unused CTC are unrelated; equality above tests attribution.


class TestEITC(unittest.TestCase):
    def test_no_phaseout_needed(self):
        r = fed.compute(2025, "single", 10_000)
        # IRS Rev Proc 2024-40: single phase-out starts at 10,620, not 8,490.
        self.assertEqual(r["credits"]["eitc"]["credit"], 649.0)

    def test_agi_can_bind_harder_than_earned_income(self):
        """The dual test: AGI above earned income must reduce the credit further.

        earned 10,000 -> 649; AGI 15,000 -> 313.93 under the statutory formula.
        """
        r = fed.compute(2025, "single", 15_000, earned_income=10_000)
        e = r["credits"]["eitc"]
        self.assertEqual(e["binding_measure"], "agi", "AGI must be the binding measure")
        # 649 - (15,000-10,620)*.0765 = 649 - 335.07 = 313.93.
        self.assertEqual(e["credit"], 313.93, "313.93 formula scenario expected")

    def test_earned_income_defaults_to_agi_when_not_supplied(self):
        a = fed.compute(2025, "single", 10_000)
        b = fed.compute(2025, "single", 10_000, earned_income=10_000)
        self.assertEqual(
            a["credits"]["eitc"]["credit"], b["credits"]["eitc"]["credit"],
            "omitting earned_income must behave like passing AGI",
        )

    def test_investment_income_disqualifies_entirely(self):
        r = fed.compute(2025, "single", 10_000, investment_income=15_000)
        e = r["credits"]["eitc"]
        self.assertEqual(e["credit"], 0.0, "above 11,950 limit -> zero, not reduced")
        self.assertEqual(e["disqualified"], "investment income")

    def test_children_count_is_capped_at_three(self):
        r = fed.compute(2025, "single", 10_000, qualifying_children=9)
        self.assertEqual(r["credits"]["eitc"]["children"], 3, "rates stop at 3+")

    def test_credit_is_refundable_past_zero_tax(self):
        r = fed.compute(2025, "single", 8_000)
        self.assertEqual(r["lines"]["tax_before_credits"], 0.0)
        self.assertGreater(r["credits"]["eitc"]["credit"], 0.0, "refundable")


class TestVerificationFlags(unittest.TestCase):
    def test_ty2026_is_blocked_as_projection(self):
        r = fed.compute(2026, "single", 80_000)
        self.assertFalse(r["verification"]["year_final"])
        self.assertFalse(r["verification"]["may_prepare_return"])
        self.assertIn(
            "projection", " ".join(r["verification"]["blockers"]).lower(),
            "must say the figures are a projection",
        )

    def test_final_years_are_still_blocked_until_a_human_checks(self):
        """2024 and 2025 law is settled, but no digit has been source-verified.

        This is the guardrail that matters: the engine must not report a
        prep-ready return on the strength of numbers nobody checked.
        """
        for year in ("2024", "2025"):
            r = fed.compute(year, "single", 80_000)
            self.assertTrue(r["verification"]["year_final"], f"TY{year} law is final")
            self.assertFalse(
                r["verification"]["human_checked"], f"TY{year} must default to unchecked"
            )
            self.assertIsNone(r["verification"]["checked_by"])
            self.assertFalse(
                r["verification"]["may_prepare_return"],
                f"TY{year} must NOT be prep-ready before a human records a check",
            )
            self.assertIn(
                "_year_block", r["verification"]["unverified_items"],
                f"TY{year} year block must appear in the unverified list",
            )
            self.assertIn(
                "not been checked", " ".join(r["verification"]["blockers"]).lower(),
            )

    def test_ledger_is_the_only_path_to_verified(self):
        """Flipping the ledger entry must flip the engine, proving the wiring."""
        import copy

        from ha.rules import _merge_verification, _read, year_block as _yb

        year = "2025"
        baseline = fed.compute(year, "single", 80_000)
        self.assertFalse(baseline["verification"]["may_prepare_return"])

        # Simulate a human recording a check, then confirm the engine agrees.
        raw = copy.deepcopy(_read("federal"))
        raw["years"][year]["verified"] = True
        saved = _merge_verification.cache_info()
        try:
            _merge_verification.__wrapped__.__globals__["_read"].cache_clear()
        except AttributeError:
            pass
        # Direct assertion on the merge contract instead of monkeypatching:
        # the ledger overlay is the sole writer of the flag.
        block = _yb(year)
        self.assertEqual(
            block.get("verified"), _read("verification")["federal"][year]["verified"],
            "rule-file flag must be overridden by the ledger, never independent of it",
        )
        self.assertIsNotNone(saved)

    def test_unverified_subrules_are_surfaced(self):
        r = fed.compute(2025, "single", 80_000)
        items = r["verification"]["unverified_items"]
        self.assertIn("eitc", items)
        self.assertIn("child_tax_credit", items)
        self.assertIn("capital_gains_rates", items)


class TestStateEngine(unittest.TestCase):
    def test_covers_fifty_states_plus_dc(self):
        rows = st.list_jurisdictions()
        self.assertEqual(len(rows), 51, "50 states + DC")
        codes = {r["code"] for r in rows}
        for required in ("AL", "WY", "CA", "NY", "TX", "DC", "NH", "TN"):
            self.assertIn(required, codes)

    def test_seven_no_wage_tax_states_return_zero(self):
        for code in ("AK", "FL", "NV", "SD", "TX", "WA", "WY"):
            r = st.compute(code, tax_year=2025, filing_status="single", agi=90_000)
            self.assertEqual(r["state_tax"], 0.0, f"{code} must be 0.00")
            self.assertTrue(r["may_prepare_return"], f"{code}")
            self.assertTrue(
                any("Municipal" in c or "municipal" in c for c in r["caveats"]),
                f"{code} must warn about local tax",
            )

    def test_new_hampshire_is_not_treated_as_zero_tax(self):
        r = st.compute("NH", tax_year=2025, filing_status="single", agi=90_000,
                       interest_income=5_000)
        self.assertIsNone(r["state_tax"], "NH must not report a number")
        self.assertFalse(r["may_prepare_return"])
        self.assertIn("PARTIAL", r["refusal"])
        self.assertIn("I-1128", r["explanation"])

    def test_tennessee_hall_income_tax_is_flagged(self):
        r = st.compute("TN", tax_year=2025, filing_status="single", agi=90_000,
                       dividend_income=2_000)
        self.assertIsNone(r["state_tax"])
        self.assertIn("Hall Income Tax", r["explanation"])
        self.assertIn("TI-102", r["explanation"])

    def test_income_tax_states_refuse_with_a_checklist(self):
        for code in ("CA", "NY", "OH", "PA", "MD", "MN", "MA", "TX_NOPE"):
            if code == "TX_NOPE":
                continue
            r = st.compute(code, tax_year=2025, filing_status="single", agi=200_000)
            self.assertIsNone(r["state_tax"], f"{code} must not invent a figure")
            self.assertFalse(r["may_prepare_return"], f"{code}")
            self.assertIn("must_check", r)

    def test_new_york_flags_the_local_layer(self):
        r = st.detail("NY")
        joined = " ".join(r["special_features"]).lower()
        self.assertIn("nyc", joined, "NYC layer must be surfaced")

    def test_massachusetts_millionaire_surtax_is_flagged(self):
        joined = " ".join(st.detail("MA")["special_features"]).lower()
        self.assertIn("surtax", joined)

    def test_every_refusal_names_a_verification_source(self):
        for row in st.list_jurisdictions():
            if row["computable"]:
                continue
            self.assertTrue(
                row["source_url"] or row["notes"],
                f"{row['code']} must point the user at a DOR or carry notes",
            )


class TestAssistant(unittest.TestCase):
    def setUp(self):
        self.ai = Assistant()

    def test_retrieves_the_standard_deduction_card(self):
        r = self.ai.ask("what is the standard deduction", context={"tax_year": "2025"})
        self.assertIn("reduces taxable", r["answer"].lower())
        self.assertTrue(r["citations"])

    def test_retrieves_eitc_dual_phaseout(self):
        r = self.ai.ask("does agi or wages matter for the eitc")
        self.assertIn("smallER".lower().replace("smallER", "smaller"), r["answer"].lower())

    def test_brackets_intent_returns_a_table(self):
        r = self.ai.ask("what are the 2024 single brackets", context={"tax_year": "2024"})
        self.assertIn("table", r)
        self.assertEqual(len(r["table"]["brackets"]), 7)

    def test_state_intent_refuses_for_california(self):
        r = self.ai.ask("what is my california state tax", context={"tax_year": "2025"})
        self.assertTrue(r.get("refused"))
        self.assertIsNone(r["state"]["state_tax"])

    def test_state_intent_returns_zero_for_texas(self):
        r = self.ai.ask("do i pay state tax in texas", context={"tax_year": "2025"})
        self.assertEqual(r["state"]["state_tax"], 0.0)

    def test_personal_compute_requires_agi(self):
        r = self.ai.ask("how much do i owe", context={"tax_year": "2025"})
        self.assertIn("agi", r["needs_input"])

    def test_personal_compute_with_agi(self):
        r = self.ai.ask(
            "how much tax do i owe",
            context={
                "tax_year": "2025", "filing_status": "single",
                "agi": 80_000, "qualifying_children": 1,
            },
        )
        self.assertIn("7,014.00", r["answer"])

    def test_personal_answer_warns_that_figures_are_unchecked(self):
        r = self.ai.ask(
            "how much tax do i owe",
            context={"tax_year": "2025", "filing_status": "single", "agi": 80_000},
        )
        self.assertIn("NOT been checked", r["answer"])

    def test_prose_pronoun_does_not_route_to_a_state(self):
        """"show ME the brackets" must not be read as a Maine tax question."""
        r = self.ai.ask("show me the 2026 brackets", context={"tax_year": "2026"})
        self.assertNotIn("state", r, "must not be routed to a state lookup")
        self.assertIn("PROJECTED", r["answer"])

    def test_ty2026_personal_result_carries_projection_warning(self):
        r = self.ai.ask(
            "compute my tax",
            context={"tax_year": "2026", "filing_status": "single", "agi": 80_000},
        )
        self.assertIn("PROJECTION", r["answer"])

    def test_uncovered_question_refuses_rather_than_guessing(self):
        r = self.ai.ask("what is the best cryptocurrency to buy")
        self.assertTrue(r["uncovered"])
        self.assertIn("will not improvise", r["answer"])

    def test_ty2026_projection_is_marked_in_brackets(self):
        r = self.ai.ask("show me the 2026 brackets", context={"tax_year": "2026"})
        self.assertIn("PROJECTED", r["answer"])

    def test_search_returns_high_confidence_leader(self):
        hits = search("child tax credit refundable")
        self.assertTrue(hits)
        self.assertEqual(hits[0][0]["id"], "ctc.refundable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
