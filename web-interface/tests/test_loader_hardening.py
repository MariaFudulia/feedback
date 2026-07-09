"""Loader robustness: _load_real must skip malformed pickle records, not crash import.

Builds a tiny synthetic pickle export in a tmp dir (no private data needed) with a couple
of deliberately-broken records, and asserts the good course still resolves while the bad
ones are skipped + counted.
"""

import os
import pickle

import taxonomy


def _write(d, cats, courses, feedbacks):
    for name, obj in (("categories", cats), ("courses", courses), ("feedbacks", feedbacks)):
        with open(os.path.join(d, f"{name}.p"), "wb") as f:
            pickle.dump(obj, f)


def test_load_real_skips_malformed_records(tmp_path):
    cats = [
        {"id": 7, "name": "03. Automatică şi Calculatoare", "path": "/7", "parent": None},
        {"id": 10, "name": "Licență", "path": "/7/10", "parent": 7},
        {"id": 11, "name": "Domeniul Calculatoare (CTI)", "path": "/7/10/11", "parent": 10},
        {"id": 12, "name": "Anul 1", "path": "/7/10/11/12", "parent": 11},
        {"name": "no id here"},  # malformed category -> skipped, not fatal
    ]
    courses = [
        {
            "id": 100,
            "shortname": "03-ACS-L-CTI-A1-S1-GOOD-CA",
            "fullname": "03-ACS-L-CTI-A1: Good Course (Seria CA - 2024)",
            "categoryid": 12,
        },
        {"id": 101, "shortname": "03-ACS-L-CTI-A1-S1-BAD-CB", "categoryid": 12},  # missing fullname
        {"shortname": "no-id", "fullname": "x", "categoryid": 12},  # missing id
    ]
    feedbacks = [{"id": 900, "course": 100}, {"id": 901, "course": 101}, {"note": "no keys"}]
    _write(str(tmp_path), cats, courses, feedbacks)

    offerings, _dom, _spec, _years, stats = taxonomy._load_real(str(tmp_path), 7)

    # the good course resolved; the two broken course records were skipped + counted, no crash
    assert len(offerings) == 1
    assert offerings[0]["denumire"] == "Good Course"
    assert offerings[0]["serie"] == "CA"
    assert offerings[0]["ciclu"] == "L" and offerings[0]["domeniu"] == "CTI" and offerings[0]["an"] == 1
    assert stats["malformed"] == 2  # missing-fullname + missing-id
