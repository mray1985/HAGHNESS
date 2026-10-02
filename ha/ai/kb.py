"""HA Tax Software — embedded knowledge base.

A corpus of rule cards. Each card carries its own authority citation and a
verified flag, so an answer can be traced back to a source and the assistant
can be honest about which statements are settled law and which need checking.

This is a knowledge base, not a language model. It is deterministic, runs
offline, and cannot hallucinate: every sentence it can emit exists here or is
assembled from the engine in ha/engine/. If a question is not covered, the
assistant says so rather than improvising.
"""

from __future__ import annotations

from typing import Any

#: verified=True  -> figure taken from a final authority cited in the card
#: verified=False -> structure is right, figures need confirmation at source
CARDS: list[dict[str, Any]] = [
    {
        'id':'rental.augusta','topic':'rental property',
        'keywords':['augusta','augsta','280a','14 day rental','rent home'],
        'questions':['what is the augusta rule','what is the augsta rule'],
        'verified':False,
        'citation':'https://www.irs.gov/taxtopics/tc415 ; IRC 280A(g)',
        'answer':('The Augusta rule is the nickname for IRC 280A(g). If a dwelling is used as your residence and rented for fewer than 15 days during the tax year, the rental income is excluded and rental expenses are not deductible. Count all rental days for the year, not 14 days per renter.\n\n'
                  'A business renting an owner’s home is a separate deduction question: a genuine business purpose, reasonable rent, documentation and related-party rules need review. The nickname does not automatically make a business deduction allowable. Tell me the tax year, rental days, personal use and who is renting the property.'),
    },
    # ---------------------------------------------------------------- scope
    {
        "id": "scope.what_this_is",
        "topic": "scope",
        "keywords": ["what", "does", "this", "software", "do", "compute", "calculate", "tool"],
        "questions": ["what can you calculate", "what does this do", "what do you compute"],
        "verified": True,
        "citation": "engine/federal.py module docstring",
        "answer": (
            "I compute Form 1040 core mechanics only: standard deduction, ordinary income "
            "brackets, preferential capital-gain stacking, the child tax credit, and the "
            "earned income tax credit, for TY2024, TY2025 and TY2026.\n\n"
            "I do NOT compute AGI. AGI is an input I am given, because above-the-line "
            "adjustments are where real returns go wrong. I also do not handle itemized "
            "deductions, Schedules 1-4, AMT, NIIT, Section 199A, or Form 8962 repayment."
        ),
    },
    {
        "id": "scope.no_filing",
        "topic": "scope",
        "keywords": ["file", "filing", "efile", "transmit", "submit", "irs", "send", "irsdirect"],
        "questions": ["can you file my return", "do you send to the irs", "can you efile"],
        "verified": True,
        "citation": "compliance/__init__.py",
        "answer": (
            "No. I have no network egress in the calculation path. There is no e-file, no "
            "MeF export, and nothing is transmitted anywhere. I am a calculation aid, not "
            "return preparation, and a return signed on my output alone would be "
            "unauthorized practice under Circular 230."
        ),
    },
    {
        "id": "scope.ty2026",
        "topic": "scope",
        "keywords": ["2026", "final", "projected", "ready", "accurate", "current", "estimate"],
        "questions": ["is 2026 final", "can i file 2026", "are 2026 numbers final"],
        "verified": True,
        "citation": "rules/federal.json -> years.2026",
        "answer": (
            "The basic 2026 ordinary-income brackets and standard deductions are "
            "published in IRS Rev. Proc. 2025-32 and have been updated here. Other "
            "rules and complete-return calculations still require independent "
            "verification. HATax continues to block return preparation."
        ),
    },

    # ------------------------------------------------- standard deduction
    {
        "id": "stdded.general",
        "topic": "standard_deduction",
        "keywords": ["standard", "deduction", "take", "claim", "amount", "default"],
        "questions": ["what is the standard deduction", "how much is the standard deduction"],
        "verified": True,
        "citation": "IRC 63(c); Rev. Proc. 2023-34 / 2024-40",
        "answer": (
            "The standard deduction reduces taxable income; it is NOT a tax credit and does "
            "not reduce tax dollar-for-dollar. You get it whether or not you itemize, so "
            "itemizing only pays off if your total itemized deductions exceed the standard "
            "deduction for your filing status."
        ),
    },
    {
        "id": "stdded.itemize_compare",
        "topic": "standard_deduction",
        "keywords": ["itemize", "itemizing", "vs", "versus", "compare", "worth", "better", "mortgage", "salt"],
        "questions": ["should i itemize", "is itemizing worth it", "itemize or standard"],
        "verified": True,
        "citation": "IRC 63",
        "answer": (
            "Itemize only if your total itemized deductions EXCEED the standard deduction. "
            "The standard deduction is not lost if you itemize - the deduction is still "
            "available, it is just not added on top. The usual drivers are state and local "
            "income tax (capped at $10,000 under SALT, with a 5-year carryforward), "
            "qualifying home mortgage interest, and charitable giving. Above roughly "
            "$400-500 of charitable giving the standard deduction is almost always the "
            "better answer on a pure arithmetic basis."
        ),
    },

    # ------------------------------------------------------------- brackets
    {
        "id": "brackets.general",
        "topic": "brackets",
        "keywords": ["bracket", "brackets", "marginal", "rate", "rates", "tier", "progressive"],
        "questions": ["what are the tax brackets", "what are my brackets", "how do brackets work"],
        "verified": True,
        "citation": "IRC 1; annual revenue procedure",
        "answer": (
            "Federal rates are progressive: each bracket applies only to the income that "
            "falls inside it, not to all your income. Moving from 12% to 22% does not tax "
            "everything you earn at 22%.\n\n"
            "Top rate is 37% for every filing status. Rates are indexed annually for "
            "inflation under IRC 1(f)."
        ),
    },
    {
        "id": "brackets.marginal_vs_effective",
        "topic": "brackets",
        "keywords": ["marginal", "effective", "average", "difference", "mean"],
        "questions": ["marginal vs effective rate", "what is my effective rate", "difference between marginal and average"],
        "verified": True,
        "citation": "Form 1040 Worksheet 1-5",
        "answer": (
            "Your marginal rate is the rate on your LAST dollar of taxable income. Your "
            "effective rate is total tax divided by total income.\n\n"
            "The gap is normal. A single filer with $80,000 of taxable income sits in the "
            "22% marginal bracket but pays roughly 16% effective. The effective rate is the "
            "one to plan against."
        ),
    },
    {
        "id": "brackets.indexing",
        "topic": "brackets",
        "keywords": ["index", "indexed", "inflation", "cola", "increase", "change", "annually"],
        "questions": ["why do brackets change every year", "are brackets indexed"],
        "verified": True,
        "citation": "IRC 1(f)(3), 63(c)(4)",
        "answer": (
            "Brackets, standard deduction, and several credit parameters are indexed for "
            "inflation automatically under IRC 1(f) using chained CPI, and the revenue "
            "procedure each autumn publishes the resulting tables. A tax year that has not "
            "had its revenue procedure published has no final figures yet."
        ),
    },

    # ------------------------------------------------------------------ CTC
    {
        "id": "ctc.general",
        "topic": "child_tax_credit",
        "keywords": ["child", "children", "tax", "credit", "ctc", "2000", "2200", "per", "dependent"],
        "questions": ["how much is the child tax credit", "what is the child tax credit", "ctc amount"],
        "verified": False,
        "citation": "IRC 24(h)(2) as amended by OBBBA P.L. 119-21 Sec. 101",
        "answer": (
            "The child tax credit is $2,000 per qualifying child for TY2024 and $2,200 for "
            "TY2025, increased by the One Big Beautiful Bill Act. A qualifying child must be "
            "under 17 at the END of the year.\n\n"
            "It begins to phase out at modified AGI of $200,000 (single / HOH / MFS) or "
            "$400,000 (MFJ), reduced by $50 for each $1,000 of MAGI over the threshold OR "
            "FRACTION of a $1,000.\n\n"
            "It is only nonrefundable up to the tax you owe. Excess is carried forward as an "
            "advance payment, not refunded."
        ),
    },
    {
        "id": "ctc.refundable",
        "topic": "child_tax_credit",
        "keywords": ["refund", "refundable", "overpaid", "excess", "carry", "forward", "w2", "earned"],
        "questions": ["can i get the child tax credit refunded", "is the ctc refundable"],
        "verified": True,
        "citation": "IRC 24",
        "answer": (
            "No. Unused child tax credit is NOT refundable. It carries forward as an advance "
            "payment against future liability. Only 85% of the unused credit carries forward, "
            "and the carryforward cannot exceed $1,700 per child (indexed) for a given year.\n\n"
            "To make the credit usable, both parents generally need earned income - at least "
            "enough to cover the withholding. Withhold too little and you get no refund and "
            "the credit is wasted."
        ),
    },
    {
        "id": "ctc.qualifying_child",
        "topic": "child_tax_credit",
        "keywords": ["qualifying", "child", "depend", "age", "17", "who", "claim", "custody"],
        "questions": ["who counts as a qualifying child", "what age is a qualifying child"],
        "verified": True,
        "citation": "IRC 24(c)(2)",
        "answer": (
            "Four tests, all required: relationship (child, stepchild, grandchild, sibling, "
            "etc.), age under 17 at year end, residency more than half the year, and joint "
            "return support if the person is married (unless the exception applies). The "
            "child must not have income above the annual threshold - $1,300 for 2024.\n\n"
            "Tiebreakers follow a fixed order when two people qualify: if the parents have "
            "equal time, whoever has the higher AGI claims the child."
        ),
    },

    # ----------------------------------------------------------------- EITC
    {
        "id": "eitc.general",
        "topic": "eitc",
        "keywords": ["eitc", "earned", "income", "tax", "credit", "low", "income", "refundable"],
        "questions": ["how much is the eitc", "what is the eitc", "do i qualify for eitc"],
        "verified": False,
        "citation": "IRC 32",
        "answer": (
            "The EITC is fully refundable - it comes off even if you owe no tax - and is the "
            "single largest working-family credit in the code. Maximum credit for TY2024: "
            "$632 with no qualifying children, $421 with one, $696 with two, $783 with three "
            "or more. For TY2025: $649 / $432 / $714 / $803.\n\n"
            "It phases out on BOTH earned income AND AGI, and the worse of the two applies. "
            "Engagement and full-time student status also apply to anyone without a "
            "qualifying child. Every state with a state EITC computes it as a percentage of "
            "the federal credit."
        ),
    },
    {
        "id": "eitc.dual_phaseout",
        "topic": "eitc",
        "keywords": ["phaseout", "phase", "agi", "gross", "wages", "self", "employment"],
        "questions": ["how does eitc phase out", "eitc phaseout agi or wages"],
        "verified": True,
        "citation": "IRC 32(a)(2)",
        "answer": (
            "Both. The credit is computed once using earned income and again using AGI, and "
            "the SMALLER of the two results is your EITC. Code that only phases out on "
            "earned income overstates the credit for anyone with a large capital gain, a "
            "taxable Social Security benefit, or an unusual deduction.\n\n"
            "Self-employment net earnings count 92.35% as earned income."
        ),
    },
    {
        "id": "eitc.investment_income",
        "topic": "eitc",
        "keywords": ["investment", "interest", "dividend", "capital", "gain", "disa", "disqualify"],
        "questions": ["do capital gains disqualify me from eitc", "what is the eitc investment income limit"],
        "verified": False,
        "citation": "IRC 32(c)(5) (DISA)",
        "answer": (
            "Yes, above a threshold. Disqualified income is the sum of interest, dividends, "
            "and net capital gain. Exceed the limit ($11,600 single / $23,200 MFJ for 2024) "
            "and the EITC is zero, not reduced. Retirement distributions and tax-exempt "
            "interest count too."
        ),
    },

    # ------------------------------------------------------- capital gains
    {
        "id": "capgains.general",
        "topic": "capital_gains",
        "keywords": ["capital", "gain", "gains", "rate", "15", "20", "0", "stock", "crypto", "sell"],
        "questions": ["what is the capital gains tax rate", "how is capital gains taxed"],
        "verified": False,
        "citation": "IRC 1(h); Schedule D",
        "answer": (
            "Long-term gains on assets held more than 12 months get preferential 0% / 15% / "
            "20% rates instead of your ordinary rate. Short-term gains (held a year or less) "
            "are taxed as ordinary income - no break at all.\n\n"
            "The 0% band is measured against your TOTAL taxable income, and the gain inside it "
            "is taxed at genuinely zero. That is the point of the band: it stops a modest gain "
            "from pushing you into a higher ordinary bracket. So a single filer with $5,000 of "
            "ordinary income and a $10,000 long-term gain owes tax on $5,000, not $15,000.\n\n"
            "Once your ordinary income is already above the 0% ceiling there is no headroom "
            "left and gains start at 15% immediately. On $65,000 of ordinary income a single "
            "filer is already past the 2025 ceiling, so every dollar of gain is 15%.\n\n"
            "Crypto is property. Disposing of it is a capital gain or loss, and the tax year "
            "the property is disposed of is when the gain or loss is reported."
        ),
    },
    {
        "id": "capgains.hold_period",
        "topic": "capital_gains",
        "keywords": ["hold", "holding", "period", "long", "term", "short", "12", "year", "wash", "sale"],
        "questions": ["how long do i have to hold", "long term vs short term", "what is a wash sale"],
        "verified": True,
        "citation": "IRC 1222, 1091",
        "answer": (
            "More than 12 months is long-term; exactly 12 months or less is short-term. The "
            "clock runs day by day from the day AFTER acquisition through and including the "
            "day of disposition.\n\n"
            "A wash sale - buying a substantially identical security within 30 days before or "
            "after the sale - defers the loss and adds the disallowed loss to the basis of the "
            "replacement. The 30-day window spans both dates, so a purchase one day after the "
            "sale still triggers it."
        ),
    },
    {
        "id": "capgains.netting",
        "topic": "capital_gains",
        "keywords": ["net", "loss", "netting", "carryforward", "capital", "loss", "3", "dollar", "gain"],
        "questions": ["how do capital losses work", "can i net capital losses", "capital loss carryforward"],
        "verified": True,
        "citation": "IRC 1211, 1212, 165(f)",
        "answer": (
            "Losses net against gains within the same character bucket - short against short, "
            "long against long. If losses exceed gains in one bucket, the excess nets against "
            "the other bucket, and if total losses still exceed total gains, $3,000 may be "
            "deducted against ordinary income.\n\n"
            "The remaining $3,000 loss carries FORWARD year to year with no expiration. You do "
            "not lose it."
        ),
    },

    # ------------------------------------------------------------ deadlines
    {
        "id": "deadline.april15",
        "topic": "deadlines",
        "keywords": ["deadline", "due", "date", "when", "file", "april", "15", "late", "penalty"],
        "questions": ["what is the filing deadline", "when is my return due", "what is the due date"],
        "verified": True,
        "citation": "IRC 6072",
        "answer": (
            "April 15 for a calendar-year individual, which is 15 days after the year ends. "
            "TY2024 was due 2025-04-15, TY2025 is due 2026-04-15, TY2026 is due 2027-04-15.\n\n"
            "Failing to file is far more expensive than failing to pay. The failure-to-file "
            "penalty is 5% of the unpaid tax PER MONTH (or ALL of it if under 100 days); "
            "failure-to-pay is 0.5% per month. But the IRS generally reduces the failure-to-"
            "file penalty to 0.5% when a valid failure-to-pay penalty was also applied."
        ),
    },
    {
        "id": "deadline.extension",
        "topic": "deadlines",
        "keywords": ["extension", "extend", "october", "oct", "10", "late", "more", "time", "form", "4868"],
        "questions": ["how do i get an extension", "does an extension give me more time to pay"],
        "verified": True,
        "citation": "IRC 6081; Form 4868",
        "answer": (
            "Form 4868 extends the time to FILE to October 15, and it is essentially "
            "automatic - a single request on or before the deadline.\n\n"
            "IT DOES NOT EXTEND THE TIME TO PAY. Any balance due still carries interest from "
            "the original April date. Six months is not six months of relief on money you owe."
        ),
    },
    {
        "id": "deadline.filing_requirement",
        "topic": "deadlines",
        "keywords": ["have", "to", "file", "required", "threshold", "need", "must", "obligated", "gross", "income"],
        "questions": ["do i have to file", "do i have to file if i lost money", "when is filing not required"],
        "verified": False,
        "citation": "IRC 6012; annual revenue procedure",
        "answer": (
            "Generally, gross income must exceed the standard deduction plus $400 (or $1,000 "
            "both if age 65+). For TY2024 that is $15,000 for a single filer under 65, and "
            "$16,950 for a single filer 65 or older. The thresholds are higher for MFJ, HOH "
            "and QSS.\n\n"
            "Important: a LOSS does not excuse you. The threshold tests GROSS income before "
            "any losses. If you lost $30,000 but had $80,000 of gross income, you still had "
            "to file - and filing is how you claim the loss."
        ),
    },

    # ---------------------------------------------------------- SE / wages
    {
        "id": "se.rate",
        "topic": "self_employment",
        "keywords": ["self", "employed", "selfemployment", "freelance", "1099", "rate", "15.3", "se", "tax"],
        "questions": ["what is self employment tax", "how much is self employment tax"],
        "verified": True,
        "citation": "IRC 1402, 1401; Schedule SE",
        "answer": (
            "15.3% (12.4% Social Security + 2.9% Medicare) on 92.35% of net earnings from "
            "self-employment. The 7.65% reduction reflects the employer-equivalent portion of "
            "the FICA that you would have had withheld if you were an employee.\n\n"
            "The Social Security portion has a cap on a per-individual basis. The Medicare "
            "portion has NO cap. If you have W-2 wages plus self-employment income, the "
            "wages absorb the Social Security cap first. The threshold for owing anything at "
            "all is $400 of net earnings."
        ),
    },
    {
        "id": "se.estimated_payments",
        "topic": "self_employment",
        "keywords": ["estimated", "quarterly", "payment", "owe", "underpaid", "penalty", "safe", "harbor", "withhold"],
        "questions": ["do i need to make estimated payments", "when do i pay quarterly", "underpayment penalty"],
        "verified": True,
        "citation": "IRC 6654",
        "answer": (
            "Generally yes if you expect to owe $1,000 or more after withholding and credits - "
            "the safe harbor is 90% of the current year OR 100% of the prior year (110% if "
            "prior-year AGI exceeded $150,000, $75,000 MFJ).\n\n"
            "1099 payers do not withhold. A W-2 employer does. A $60,000 1099 job with zero "
            "withholding means you likely owe on both income AND self-employment tax."
        ),
    },
    {
        "id": "w2.versus_1099",
        "topic": "self_employment",
        "keywords": ["w2", "w-2", "1099", "1099k", "difference", "employee", "contractor", "classification"],
        "questions": ["what is the difference between a w2 and 1099", "does a 1099 count as income"],
        "verified": True,
        "citation": "IRC 3121; Form SS-8 / SS-4",
        "answer": (
            "Both are income, reported on Form 1040. The difference is withholding and payroll "
            "tax: a W-2 payer withholds income tax and both halves of FICA, and shows your "
            "Medicare wages in box 3. A 1099 payer generally withholds NOTHING, no Social "
            "Security, and no Medicare - you compute the self-employment tax yourself.\n\n"
            "Employee vs independent-contractor status is decided by common-law control test, "
            "not by what the paperwork says. The IRS Form SS-8 is how you get an official "
            "determination. A 1099 issued to someone who should have been a W-2 employee does "
            "not change the underlying classification."
        ),
    },
    {
        "id": "w2.forms_match",
        "topic": "documents",
        "keywords": ["match", "forms", "1099", "w2", "all", "every", "missing", "unreported", "notice", "cp2000"],
        "questions": ["do i have to report all my 1099s", "what if a 1099 is wrong", "cp2000 notice"],
        "verified": True,
        "citation": "IRC 6011; Form 1099 instructions",
        "answer": (
            "Yes - all of them. A $1,200 1099-NEC and a $900 one both go on the return. There "
            "is no de minimis exclusion on information returns.\n\n"
            "The IRS matches third-party data against what you filed. A mismatch produces a CP2000 "
            "notice. If a 1099 is wrong, correct it with the ISSUER first, then file the return "
            "consistent with the corrected form. Filing against an obviously erroneous 1099 is a "
            "position you may have to defend."
        ),
    },

    # ------------------------------------------------------ AMT and other
    {
        "id": "amt.general",
        "topic": "amt",
        "keywords": ["amt", "alternative", "minimum", "tax", "form", "6251", "exemption", "itemize"],
        "questions": ["what is the amt", "do i need to file form 6251", "alternative minimum tax"],
        "verified": True,
        "citation": "IRC 55, 56, 57; Form 6251",
        "answer": (
            "The AMT is a parallel 20% tax computed on a modified base that disallows most "
            "exemptions and deductions - it does NOT disallow the standard deduction, and the "
            "AMT exemption is far more generous than the regular one.\n\n"
            "It is NOT extra tax added to your normal bill. You pay the LARGER of your regular "
            "tax or the AMT, then subtract applicable credits. Most people with large "
            "itemized deductions, high SALT, or large exemptions never see it. Form 6251 is "
            "triggered by the AMT checkbox on Form 1040 line 1."
        ),
    },
    {
        "id": "deductions.standard_not_credit",
        "topic": "deductions",
        "keywords": ["standard", "credit", "difference", "reduce", "tax", "dollars", "worth", "value"],
        "questions": ["is the standard deduction a credit", "does the standard deduction reduce my tax"],
        "verified": True,
        "citation": "IRC 63",
        "answer": (
            "A deduction reduces taxable INCOME, then you are taxed on what is left. A credit "
            "reduces your tax directly. So a $1,000 deduction is only worth $1,000 times your "
            "marginal rate - $370 at 37%, $100 at 10%.\n\n"
            "This is why income location matters. A deduction is worth more in a high bracket, "
            "and a dollar of credit is worth a full dollar everywhere."
        ),
    },
    {
        "id": "accounts.order",
        "topic": "deductions",
        "keywords": ["order", "which", "first", "retirement", "hsa", "traditional", "ira", "401k", "sequence", "precedence"],
        "questions": ["what order should i make deductions", "should i max my 401k or hsa", "which deduction first"],
        "verified": True,
        "citation": "IRC 401(k), 408, 220",
        "answer": (
            "The exception is HSA contributions: those are effectively irrevocable once made "
            "and should generally be FUNDED FIRST, because employer contributions can be "
            "replaced by an employee adjustment and an employer can change the election for the "
            "next year.\n\n"
            "Then: match on a 401(k) (an immediate 100% return on the match, beating any tax "
            "rate you can pay); then the HSA to its limit; then traditional pre-tax "
            "contributions if you are below the 22% bracket; then Roth if above it, since Roth "
            "conversions cost you the deduction permanently. Backdoor Roth only makes sense if "
            "you are already at or near the income limit, and it is not free - the conversion "
            "is fully taxable."
        ),
    },
    {
        "id": "records.how_long",
        "topic": "records",
        "keywords": ["records", "keep", "how", "long", "years", "retain", "document", "backup", "audit"],
        "questions": ["how long should i keep tax records", "record retention", "when can i be audited"],
        "verified": True,
        "citation": "IRC 6001; Form 4506",
        "answer": (
            "Generally keep records at least 3 years from the filing date. The normal IRS "
            "assessment window is 3 years, and it is unlimited if you omitted more than 25% of "
            "your gross income. Fraud has no statute of limitations at all.\n\n"
            "Practical guidance: keep supporting documents (W-2s, 1099s, 1098s, K-1s, brokerage "
            "1099-B/8949 detail, real estate closing statements, charitable receipts) until the "
            "3-year period has run. Keep the filed return and your payment confirmation "
            "indefinitely - Form 4506 is how you get a copy years later, and it is far easier "
            "to just have it. Back up off-machine; ransomware and house fires are real."
        ),
    },
    {
        "id": "audit.who_gets",
        "topic": "audit",
        "keywords": ["audit", "audited", "cp2000", "notice", "selected", "random", "risk", "trigger", "letter"],
        "questions": ["who gets audited", "why did i get a cp2000", "what triggers an audit"],
        "verified": True,
        "citation": "IRC 6012; IRS audit rates",
        "answer": (
            "There is a random component to the National Research Program, so audits are not "
            "entirely targeted. But large or complex returns attract attention, as do returns "
            "with a mismatch between reported income and information returns, large charitable "
            "deductions, big unreported cash, or a very large refund. The earned income credit, "
            "child tax credit, education credits, and retirement savings are all audited at "
            "disproportionate rates because the credits are large relative to the return value."
        ),
    },
    {
        "id": "dependents.credit",
        "topic": "dependents",
        "keywords": ["dependent", "credit", "500", "3500", "qualifying", "child", "claim", "income"],
        "questions": ["can i claim a dependent", "dependent tax credit", "how many dependents can i claim"],
        "verified": False,
        "citation": "IRC 21",
        "answer": (
            "A dependent must be a qualifying child (the four tests above) OR a qualifying "
            "relative who lives with you all year and has gross income under the annual "
            "threshold (the dependent tax credit test) - a qualifying child is NOT subject to "
            "the gross income test.\n\n"
            "The credit is $500 for a qualifying child and $300 for a qualifying relative. If "
            "you are eligible for the child tax credit you generally want to claim the child as "
            "a dependent for the child tax credit instead - they are separate claims for the "
            "same person."
        ),
    },
    {
        "id": "hsa.general",
        "topic": "accounts",
        "keywords": ["hsa", "health", "savings", "account", "contribution", "limit", "triple", "tax"],
        "questions": ["what is an hsa", "hsa contribution limit", "is an hsa tax free"],
        "verified": False,
        "citation": "IRC 220; Rev. Proc. 2023-34 / 2024-40",
        "answer": (
            "The only account that is simultaneously tax-free going IN, tax-free growing, and "
            "tax-free coming OUT for qualified medical expenses - and that is only true because "
            "the account is spent on medical care. A non-qualified distribution is income plus "
            "a 20% penalty.\n\n"
            "Contributions are limited by your HDHP deductible and can be made by anyone on your "
            "behalf, in addition to employer contributions. You can contribute to a spouse's "
            "spouse-ineligible plan but not a general-purpose FSA. The limit is prorated if you "
            "were eligible for only part of the year."
        ),
    },
    {
        "id": "states.no_tax",
        "topic": "state",
        "keywords": ["state", "which", "states", "tax", "none", "zero", "no", "income"],
        "questions": ["which states have no income tax", "do i pay state tax in texas"],
        "verified": True,
        "citation": "State enactments; engine/states.py",
        "answer": (
            "Seven states levy no tax on wage income: Alaska, Florida, Nevada, South Dakota, "
            "Texas, Washington and Wyoming.\n\n"
            "IMPORTANT: two more are commonly lumped in and are WRONG. New Hampshire and "
            "Tennessee do not tax wages, but both tax interest and dividends - New Hampshire "
            "on Form I-1128, Tennessee as the Hall Income Tax on Form TI-102. A filer with "
            "only investment income can still owe in both states.\n\n"
            "And none of the nine answers the local question. Municipal income taxes apply "
            "separately in New York City, across Ohio municipalities, in Maryland counties, "
            "and in parts of Pennsylvania."
        ),
    },
    {
        "id": "states.why_no_numbers",
        "topic": "state",
        "keywords": ["state", "calculate", "compute", "number", "my", "bracket", "why", "not", "refuse"],
        "questions": ["why can't you calculate my state tax", "can you do my state return", "compute my state taxes"],
        "verified": True,
        "citation": "engine/states.py module docstring",
        "answer": (
            "Because I do not have verified bracket data for those jurisdictions, and I will "
            "not return a number I cannot source.\n\n"
            "State income tax law is not a national dataset. 41 states and DC each enact, "
            "index, sunset, and amend independently, many on a bracket structure unrelated to "
            "the federal one. Several deduct the federal income tax, several refundable state "
            "EITCs at a percentage of the federal credit, and a growing number add a separate "
            "municipal layer the federal return never sees.\n\n"
            "Where the answer is genuinely zero, I give you zero. Where it is not, I give you "
            "the list of features a preparer must check and refuse to guess. Load verified "
            "per-year brackets into ha/rules/states.json to enable a state."
        ),
    },
    {
        "id": "misc.amended_return",
        "topic": "filing",
        "keywords": ["amended", "amend", "1040x", "mistake", "wrong", "fix", "error", "correct", "refund"],
        "questions": ["i made a mistake", "how do i amend my return", "file an amended return"],
        "verified": True,
        "citation": "IRC 6511; Form 1040-X",
        "answer": (
            "Form 1040-X. The refund statute of limitations is 3 years from the original filing "
            "date, and refunds stop being available after 3 years even if the return was wrong "
            "- the statute applies to the CLAIM, not the error. Where the IRS was in the wrong, "
            "the window is longer (2 years from when you discovered it, or 6 from the return).\n\n"
            "Processing a 1040-X can take 8-12 weeks or more, and it is well documented that "
            "amending a return the IRS is already auditing often slows the audit without "
            "changing the outcome. Coordinate before you file if you know an audit is open."
        ),
    },
    {
        "id": "misc.multiple_states",
        "topic": "state",
        "keywords": ["two", "states", "multiple", "moved", "part", "year", "resident", "domicile", "dual"],
        "questions": ["i moved to another state", "do i file in two states", "part year resident"],
        "verified": True,
        "citation": "State residency statutes; Form PIT-1Y equivalents",
        "answer": (
            "Usually yes, and it is the single most commonly mishandled state situation. You "
            "file a part-year return in each state. Domicile - your true, fixed, permanent "
            "home - controls, and the tiebreaker is usually where your family and economic "
            "ties are, NOT where you slept most nights.\n\n"
            "A handful of states have no part-year allocation and tax all income to the state "
            "of domicile. Some states give a credit for taxes paid to another state to prevent "
            "double taxation, but many cap that credit, so moving can increase your total tax "
            "even at an identical income."
        ),
    },
]

BY_ID = {card["id"]: card for card in CARDS}
