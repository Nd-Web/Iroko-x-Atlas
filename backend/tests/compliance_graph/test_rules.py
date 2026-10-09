"""Deterministic rules: taxonomy, segmentation, relations, applicability, deadlines, wording."""

from datetime import date
from types import SimpleNamespace

from services.compliance_graph import applicability, deadlines, relations, segment, taxonomy, wording
from tests.compliance_graph.factory import AMENDING_LETTER, BVN_LETTER, REVOCATION_GAZETTE


def page(text, position=0, number=1):
    return SimpleNamespace(text=text, position=position, page_number=number, locator=None)


# ─── Taxonomy ────────────────────────────────────────────────────────────────


def test_groups_expand_and_payments_are_not_ofis():
    assert taxonomy.leaves(["mfb"]) == {"unit_tier1", "unit_tier2", "state", "national"}
    ofi = taxonomy.leaves(["ofi"])
    assert {"unit_tier1", "bdc", "dfi", "pmb"} <= ofi
    assert not ofi & taxonomy.leaves(["payments"])


def test_specific_names_mask_generic_ones():
    found = taxonomy.match_addressees("Letter to all Microfinance Banks (MFBs) and Payment Service Banks")
    terms = [m.term for m in found]
    assert "microfinance banks" in terms and "payment service banks" in terms
    assert "banks" not in terms  # never re-matched inside a specific name
    assert all(m.explicit for m in found)


def test_bare_banks_is_only_a_suggestion():
    (only,) = taxonomy.match_addressees("All banks shall comply")
    assert only.codes == ("dmb", "psb") and not only.explicit


def test_typos_are_fuzzy_never_stated():
    assert not taxonomy.match_addressees("LETTER TO ALL OTHER FINANCIAL INSTITUTIIONS")
    fuzzy = taxonomy.fuzzy_addressees("LETTER TO ALL OTHER FINANCIAL INSTITUTIIONS")
    assert fuzzy and fuzzy[0].codes == ("ofi",) and not fuzzy[0].explicit


def test_returns_follow_licence():
    assert taxonomy.return_applies("cbn-monthly-prudential", ["state"])
    assert not taxonomy.return_applies("cbn-monthly-prudential", ["mmo"])
    assert taxonomy.return_applies("cbn-monthly-prudential", [])  # no profile: unchanged behaviour


# ─── Segmentation ────────────────────────────────────────────────────────────


def test_sentences_are_exact_slices_across_wrapped_lines():
    p = page(BVN_LETTER)
    sentences = segment.tag(segment.segment([p]))
    for s in sentences:
        assert p.text[s.start:s.end] == s.raw
    wrapped = next(s for s in sentences if "valid Bank Verification Number" in s.quote)
    assert wrapped.quote.startswith("All OFIs shall ensure that every customer account")
    assert "\n" in wrapped.raw  # it really spans two lines
    assert "requirement" in wrapped.tags


def test_abbreviations_do_not_end_sentences():
    p = page("Pursuant to s. 27 of BOFIA, MFBs shall file returns. No. 5 applies.\nNext item here.")
    quotes = [s.quote for s in segment.segment([p])]
    assert quotes[0] == "Pursuant to s. 27 of BOFIA, MFBs shall file returns."


def test_markup_is_masked_but_offsets_kept():
    text = '<!-- PageHeader="Our Ref: OFI/DIR/DOC/GEN/20/365" -->\n\nOFIs shall render returns monthly to the CBN.'
    (s,) = [s for s in segment.segment([page(text)]) if "render" in s.quote]
    assert s.quote == "OFIs shall render returns monthly to the CBN."
    assert text[s.start:s.end] == s.raw


def test_misspelt_licence_outranks_the_generic_word_inside_it():
    found = applicability.document_addressees([page("Ref: OFI/DIR/DOC/GEN/022/001\n\n# LETTER TO ALL MICROFINACE BANKS\n")])
    assert [(a["codes"], a["basis"]) for a in found] == [(["mfb"], "suggested")]
    exact = applicability.document_addressees([page("# LETTER TO ALL MICROFINANCE BANKS (MFBs)\n")])
    assert [(a["codes"], a["basis"]) for a in exact] == [(["mfb"], "stated")]


def test_addressee_header_lines_and_rejected_body_lines():
    text = ("Ref: OFI/DIR/CIR/GEN/17/139\n\n# LETTER TO ALL OTHER FINANCIAL INSTITUTIONS (OFIs)\n\n"
            "all banks and OFIs are required\nto forward the audited financial statements to the CBN.")
    lines = [line for _p, _a, _b, line in segment.addressee_lines([page(text)])]
    assert lines == ["LETTER TO ALL OTHER FINANCIAL INSTITUTIONS (OFIs)"]


def test_own_reference_ignores_body_citations():
    assert segment.reference_from_pages([page(BVN_LETTER)]) == "OFI/DIR/CIR/GEN/17/139"
    header = '<!-- PageHeader="OFI/DOA/CON/OFI/001/304" -->\n\nJanuary 09, 2023\n\n# LETTER TO ALL OFIs\n'
    assert segment.reference_from_pages([page(header)]) == "OFI/DOA/CON/OFI/001/304"
    body = "June 1, 2019\n\n# LETTER TO ALL OFIs\n\nFurther to our circular ref: OFISD/DIR/CIR/GEN/17/128 dated May."
    assert segment.reference_from_pages([page(body)]) is None
    assert segment.normalize_reference(" ofi / dir / cir / gen / 17 / 139. ") == "OFI/DIR/CIR/GEN/17/139"


# ─── Relations ───────────────────────────────────────────────────────────────


def _findings(text, own=None):
    sentences = segment.tag(segment.segment([page(text)]))
    return relations.deterministic_findings([s for s in sentences if "relation" in s.tags], own)


def test_revoking_licences_is_not_revoking_an_instrument():
    findings = _findings(REVOCATION_GAZETTE)
    assert [(f.relation, f.mention.key, f.basis) for f in findings] == [("issued_under", "bofia_2020", "stated")]
    assert not any(f.relation == "revokes" for f in findings)


def test_as_amended_is_a_citation_not_an_amendment():
    findings = _findings(AMENDING_LETTER, own="OFI/DIR/CIR/GEN/19/001")
    by_key = {f.mention.key: f for f in findings}
    assert by_key["OFI/DIR/CIR/GEN/17/139"].relation == "amends"
    assert by_key["OFI/DIR/CIR/GEN/17/139"].basis == "stated"
    assert by_key["mlpa_2011"].relation == "references"


def test_hereby_bound_to_target_in_the_same_clause():
    stated = _findings("The CBN hereby revokes circular OFI/DIR/CIR/GEN/17/139 with immediate effect.")
    assert stated[0].relation == "revokes" and stated[0].basis == "stated"
    split = _findings("The CBN hereby revokes the old approvals; see circular OFI/DIR/CIR/GEN/17/139 for context.")
    assert split[0].relation == "references"


def _effective(text):
    p = page(text)
    sentences = segment.tag(segment.segment([p]))
    return relations.effective_date([s for s in sentences if "effective" in s.tags], [p])


def test_effective_dates_from_own_words_or_letter_date():
    # "Effective August 1, 2017, OFIs shall not open accounts ..." dates one requirement, not the circular.
    assert _effective(BVN_LETTER) is None
    found = _effective("Ref: OFI/DIR/CIR/GEN/20/001\n\nMay 4, 2020\n\n# LETTER TO ALL OFIs\n\nThis circular takes effect immediately.")
    assert found["date"] == date(2020, 5, 4) and found["basis"] == "suggested"
    found = _effective("# LETTER TO ALL OFIs\n\nThis new provision takes effect from September 9, 2019.")
    assert found["date"] == date(2019, 9, 9) and found["basis"] == "stated"


def test_effective_dates_of_other_instruments_are_never_taken():
    reported = ("# LETTER TO ALL OFIs\n\nThe letter also stated that effective from August 1, 2017, all customers "
                "without BVN should not be allowed to make withdrawals.")
    assert _effective(reported) is None
    national = ("# LETTER TO ALL OFIs\n\nOn 28 July 2010, the Federal Executive Council approved January 1, 2012, "
                "as the effective date for adoption of IFRS in Nigeria.")
    assert _effective(national) is None


def test_commencement_note_and_attached_guidelines():
    gazette = "S. I. No. 22 of 2023\nREVOCATION OF OPERATING LICENCES\n[22nd Day of May, 2023] Commence-\nment.\nWHEREAS :"
    found = _effective(gazette)
    assert found["date"] == date(2023, 5, 22) and found["basis"] == "stated"
    cover = ("# LETTER TO ALL OFIs\n\nThe effective date for full compliance with the provisions of the guidelines is "
             "January 1, 2023 and all OFIs are expected to comply.")
    found = _effective(cover)
    assert found["date"] == date(2023, 1, 1) and found["basis"] == "suggested"
    found = _effective(cover + "\n\n## 10. Effective Date\n\nThis Guideline shall take effect from January 1, 2023")
    assert found["basis"] == "stated"  # the instrument's own words win over the cover letter's


LIST_LETTER = ("# LETTER TO ALL OFIs\n\nIn view of the foregoing, all OFIs are required to:\n\n"
               "a. Enroll their customers on or before July 31, 2017;\n\n"
               "b. Conspicuously display notices sensitizing customers on BVN in the banking hall\n\n"
               "Please be guided accordingly.\n\nSpecifically, DFIs are required to:\n\n"
               "1\\. Submit returns on all SPVs along with own regulatory returns.\n")


def test_list_items_completing_a_duty_are_candidates():
    sentences = segment.tag(segment.segment([page(LIST_LETTER)]))
    item = next(s for s in sentences if s.quote.startswith("b. Conspicuously"))
    assert "requirement" in item.tags
    assert sentences[item.lead_in].quote == "In view of the foregoing, all OFIs are required to:"
    escaped = next(s for s in sentences if "Submit returns on all SPVs" in s.quote)
    assert "requirement" in escaped.tags and sentences[escaped.lead_in].quote.startswith("Specifically, DFIs")
    closing = next(s for s in sentences if s.quote.startswith("Please be guided"))
    assert "requirement" not in closing.tags and closing.lead_in is None
    # Bare introductions are dropped as candidates; ones with a duty of their own are kept.
    assert segment.BARE_LEAD_IN.search("In view of the foregoing, all OFIs are required to:")
    assert segment.BARE_LEAD_IN.search("Finally, DFIs are required to note that:")
    assert not segment.BARE_LEAD_IN.search("all BDCs are required to provide the following information as part of "
                                           "Notes to the Accounts:")


def test_duties_restated_from_an_earlier_letter_are_history():
    text = ("# LETTER TO OTHER FINANCIAL INSTITUTIONS (OFIs)\n\nYour attention is drawn to our letter referenced: "
            "OFI/DIR/CIR/GEN/17/139 in which all OFIs were required to undertake the following:\n\n"
            "a. Enroll their customers on or before July 31, 2017;\n\n"
            "b. Conspicuously display notices sensitizing customers on BVN in the banking hall\n\n"
            "As earlier directed, OFIs are therefore required to:\n\n"
            "i.\nContinue with the submission of progress reports on BVN enrolment on a monthly basis.\n")
    sentences = segment.tag(segment.segment([page(text)]))
    restated = [s for s in sentences if s.quote.startswith(("a. Enroll", "b. Conspicuously"))]
    assert len(restated) == 2 and all("requirement" not in s.tags and "history" in s.tags for s in restated)
    current = next(s for s in sentences if "progress reports" in s.quote)
    assert "requirement" in current.tags and sentences[current.lead_in].quote.startswith("As earlier directed")


def test_titles_are_not_requirement_candidates():
    text = "# LETTER TO ALL OTHER FINANCIAL INSTITUTIONS\n\nPROHIBITION OF PLACEMENT/INVESTMENT IN FUNDS MANAGED BY " \
           "UNINSURED ENTITIES\n\nAll OFIs are required to divest from such funds."
    tagged = {s.quote: s.tags for s in segment.tag(segment.segment([page(text)]))}
    assert "requirement" not in tagged["PROHIBITION OF PLACEMENT/INVESTMENT IN FUNDS MANAGED BY UNINSURED ENTITIES"]
    assert "requirement" in tagged["All OFIs are required to divest from such funds."]


def test_letterhead_headings_do_not_hide_the_reference_or_date():
    department = ("# OTHER FINANCIAL INSTITUTIONS SUPERVISION DEPARTMENT\n\nREF: OFISD/DIR/CIR/GEN/018/217\n"
                  "January 2, 2018\n\nLETTER TO OTHER FINANCIAL INSTITUTIONS (OFIs)\n\nBody text follows.")
    assert segment.reference_from_pages([page(department)]) == "OFISD/DIR/CIR/GEN/018/217"
    assert segment.letter_date([page(department)]) == date(2018, 1, 2)
    as_heading = "# OFI/DOA/CON/ACT/004/155\n\nJune 29, 2022\n\n## LETTER TO ALL OTHER FINANCIAL INSTITUTIONS\n"
    assert segment.reference_from_pages([page(as_heading)]) == "OFI/DOA/CON/ACT/004/155"
    assert segment.letter_date([page(as_heading)]) == date(2022, 6, 29)
    in_comment = '<!-- PageHeader="May 2, 2017" -->\n\nREF:\nOFISD/DIR/CIR/GEN/17/128\n\n# LETTER TO ALL OFIs\n'
    assert segment.letter_date([page(in_comment)]) == date(2017, 5, 2)


# ─── Applicability ───────────────────────────────────────────────────────────


def test_applicability_states():
    ofi_stated = [(["ofi"], "stated", "proposed")]
    assert applicability.evaluate(["state"], [], None, ofi_stated) == "applies"
    assert applicability.evaluate(["mmo"], [], None, ofi_stated) == "not_addressed"
    assert applicability.evaluate(["state"], [], None, [(["bdc"], "stated", "proposed")]) == "not_addressed"
    assert applicability.evaluate(["state"], [], None, [(["ofi"], "suggested", "proposed")]) == "likely"
    assert applicability.evaluate(["psb"], ["dmb", "psb"], "suggested", ofi_stated) == "likely"
    assert applicability.evaluate([], [], None, ofi_stated) == "no_profile"
    assert applicability.evaluate(["state"], [], None, []) == "undetermined"
    assert applicability.evaluate(["state"], [], None, ofi_stated, decision="not_applicable") == "not_applicable"
    assert applicability.evaluate(["mmo"], [], None, [(["ofi"], "suggested", "confirmed")]) == "not_addressed"


def test_generic_subjects_inherit_the_document_addressees():
    assert applicability.obligation_addressees("Institutions") == ([], None)
    assert applicability.obligation_addressees("All MFBs") == (["mfb"], "stated")
    assert applicability.obligation_addressees("banks") == (["dmb", "psb"], "suggested")


# ─── Deadlines ───────────────────────────────────────────────────────────────


def test_deadline_rules_and_next_due():
    monthly = deadlines.parse_deadline("not later than the 10th day of the following month")
    assert monthly["kind"] == "monthly_day" and monthly["day"] == 10
    assert deadlines.next_due(monthly, date(2026, 10, 9)) == date(2026, 10, 9)  # Friday the 9th? rolls back
    assert deadlines.next_due(monthly, date(2026, 10, 12)) == date(2026, 11, 10)
    within = deadlines.parse_deadline("within seven (7) days")
    assert within == {"kind": "within", "amount": 7, "unit": "day", "working": False, "text": "within seven (7) days"}
    assert deadlines.next_due(within, date(2026, 1, 1)) is None
    fy = deadlines.parse_deadline("not later than three (3) months after the end of its accounting year")
    assert fy["kind"] == "fy_offset_months" and fy["months"] == 3
    assert deadlines.next_due(fy, date(2026, 2, 1)) == date(2026, 3, 31)
    fixed = deadlines.parse_deadline("on or before June 30, 2027")
    assert fixed["kind"] == "fixed_date" and deadlines.next_due(fixed, date(2026, 1, 1)) == date(2027, 6, 30)
    assert deadlines.parse_deadline("quarterly")["frequency"] == "quarterly"
    reporting = deadlines.parse_deadline("on or before the 14th day after the end of every reporting month")
    assert reporting["kind"] == "monthly_day" and reporting["day"] == 14
    assert deadlines.parse_deadline("on August 7, 2017") == {
        "kind": "fixed_date", "date": "2017-08-07", "text": "on August 7, 2017"}
    assert deadlines.parse_deadline("A meeting held on August 7, 2017 resolved that the industry should keep "
                                    "records of the matters discussed") is None


def test_deadlines_counted_from_the_letter_date():
    issued = date(2023, 1, 9)
    rule = deadlines.parse_deadline("within 90 days of the date of this letter", issued=issued)
    assert rule["kind"] == "fixed_date" and rule["date"] == "2023-04-09" and rule["from"] == "letter_date"
    # The model's span may stop early; the requirement's own sentence supplies the anchor.
    sentence = "Existing placements must be liquidated within 90 days of the date of this letter."
    assert deadlines.parse_deadline("within 90 days", issued=issued, sentence=sentence)["date"] == "2023-04-09"
    month = deadlines.parse_deadline("within one (1) month from the date of this circular", issued=date(2019, 4, 9))
    assert month["date"] == "2019-05-09"
    unknown = deadlines.parse_deadline("within 90 days of the date of this letter")
    assert unknown["kind"] == "within" and unknown["anchor"] == "letter"
    assert deadlines.describe(unknown) == "Within 90 days of the date of the letter"
    event = deadlines.parse_deadline("within 24 hours", sentence="STRs shall be filed within 24 hours of the suspicion.")
    assert event["kind"] == "within" and "anchor" not in event


def test_wording_screen():
    assert wording.has_verdict_wording("The institution is non-compliant with BVN rules")
    assert wording.has_verdict_wording("This control is fully compliant")
    assert not wording.has_verdict_wording("The Chief Compliance Officer reviews accounts monthly")
    assert wording.screen("We are in breach", fallback=wording.NOT_ESTABLISHED) == wording.NOT_ESTABLISHED
