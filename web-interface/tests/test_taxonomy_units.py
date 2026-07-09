"""Unit tests for taxonomy's pure parsing/classification helpers.

These lock the small functions the whole taxonomy rests on, independently of the
real data (which test_real_data covers only when present).
"""

import taxonomy


def test_parse_fullname_series_and_year():
    d, s = taxonomy._parse_fullname("03-ACS-L-A2-S1: Programare orientată pe obiecte (Seria AA - 2024)")
    assert d == "Programare orientată pe obiecte"
    assert s == "AA"


def test_parse_fullname_no_series():
    d, s = taxonomy._parse_fullname("03-ACS-L-A1-S1: Analiză matematică")
    assert d == "Analiză matematică"
    assert s is None


def test_parse_fullname_series_without_year():
    d, s = taxonomy._parse_fullname("03-ACS-M-A1: Rețele (Seria CA)")
    assert d == "Rețele"
    assert s == "CA"


def test_parse_fullname_bare_year_suffix_is_stripped():
    d, s = taxonomy._parse_fullname("03-ACS-L-A1: Fizică (2024)")
    assert d == "Fizică"
    assert s is None


def test_parse_fullname_without_colon():
    d, s = taxonomy._parse_fullname("Just A Name")
    assert d == "Just A Name"
    assert s is None


def test_curs_id_is_deterministic():
    args = ("L", "CTI", None, 2, 1, "Baze de date")
    assert taxonomy._curs_id(*args) == taxonomy._curs_id(*args)


def test_curs_id_distinguishes_names_sharing_a_long_prefix():
    # the truncation bug fixed in _curs_id: names that share a 48-char slug prefix
    # must not collide (the md5 tag disambiguates)
    n2 = "Programarea calculatoarelor și limbaje de programare 2"
    n3 = "Programarea calculatoarelor și limbaje de programare 3"
    assert taxonomy._curs_id("L", "CTI", None, 1, 1, n2) != taxonomy._curs_id("L", "CTI", None, 1, 1, n3)


def test_curs_id_separates_by_slot():
    # same name in different slots (an/sem) -> different logical courses
    a = taxonomy._curs_id("L", "CTI", None, 1, 1, "Programare")
    b = taxonomy._curs_id("L", "CTI", None, 2, 1, "Programare")
    assert a != b


def test_classify_walks_the_category_tree():
    by_cat = {
        7: {"id": 7, "name": "03. Automatică şi Calculatoare", "parent": None},
        10: {"id": 10, "name": "Licență", "parent": 7},
        11: {"id": 11, "name": "Domeniul Calculatoare (CTI)", "parent": 10},
        12: {"id": 12, "name": "Specializarea Calculatoare (CALC)", "parent": 11},
        13: {"id": 13, "name": "Anul 2", "parent": 12},
        14: {"id": 14, "name": "Semestrul 1", "parent": 13},
    }
    dom, spec = {}, {}
    d = taxonomy._classify(14, by_cat, dom, spec)
    assert d["ciclu"] == "L"
    assert d["domeniu"] == "CTI"
    assert d["specializare"] == "CALC"
    assert d["an"] == 2
    assert d["sem"] == 1
    assert dom["CTI"] == "Calculatoare (CTI)"  # label harvested, "Domeniul " stripped
    assert spec["CALC"] == "Calculatoare (CALC)"


def test_classify_without_specializare_or_semester():
    by_cat = {
        7: {"id": 7, "name": "03. AC", "parent": None},
        10: {"id": 10, "name": "Master", "parent": 7},
        11: {"id": 11, "name": "Domeniul Ingineria sistemelor (IS)", "parent": 10},
        12: {"id": 12, "name": "Anul 1", "parent": 11},
    }
    d = taxonomy._classify(12, by_cat, {}, {})
    assert d["ciclu"] == "M" and d["domeniu"] == "IS" and d["an"] == 1
    assert "specializare" not in d  # no Specializarea node in the path
    assert "sem" not in d  # no Semestrul node


def test_research_denylist_matches_master_research_only():
    deny = taxonomy._RE_RESEARCH_DENY
    assert deny.search("03-ACS-M-CTI-A2-S1-CSP-X")  # CSP
    assert deny.search("03-ACS-M-IS-A1-S2-Cercetare-Y")  # Cercetare*
    assert deny.search("03-ACS-M-CTI-A2-S2-ELD-Z")  # ELD
    # a licență course and a normal master course are NOT excluded
    assert not deny.search("03-ACS-L-CTI-A1-S1-POO-CA")
    assert not deny.search("03-ACS-M-CTI-A1-S1-BPDA-SCPD")


def test_research_denylist_in_sync_with_pipeline():
    """The deny regex duplicates the pipeline's master-research exclusion (the one
    documented coupling point). Parse the pipeline's own match lines so a change on
    either side fails here instead of drifting silently."""
    import re
    from pathlib import Path

    pipeline_src = (
        Path(__file__).resolve().parents[2] / "analysis" / "select_feedback_course_mapping.py"
    ).read_text(encoding="utf-8")
    pipeline_codes = re.findall(r're\.match\("M-\.\*-([A-Za-z]+)-"', pipeline_src)
    assert pipeline_codes, "pipeline denylist not found -- did the mapping script change shape?"

    # our alternatives, extracted from the live pattern with regex syntax stripped
    # ("Cercet[^-]*" -> literal prefix "Cercet")
    group = re.search(r"\((.*?)\)\(", taxonomy._RE_RESEARCH_DENY.pattern).group(1)
    our_prefixes = [re.sub(r"\[.*?\]\*?", "", alt) for alt in group.split("|")]

    # every code the pipeline drops, our loader drops too
    for code in pipeline_codes:
        assert taxonomy._RE_RESEARCH_DENY.search(f"03-ACS-M-A1-S1-{code}-G"), code
    # and we deny nothing the pipeline doesn't: each alternative maps onto a pipeline code
    for prefix in our_prefixes:
        assert any(code.startswith(prefix) for code in pipeline_codes), prefix
    assert len(our_prefixes) == len(set(pipeline_codes))
