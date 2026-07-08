"""Real-loader test: exercises taxonomy._load_real against the actual pickle
export when present (Claudiu's machine). Skipped in CI and on teammates'
machines that don't have the private data.

Calls the loader FUNCTION directly rather than the module singleton -- the other
test files pin the singleton to the synthetic fallback (process-global env
override + one-time _init), so the only way to test the real path is to invoke
_load_real ourselves on the true data directory.
"""

import os

import pytest

import config
import taxonomy

# true default location, independent of any FEEDBACK_DATA_DIR test override
_REAL_DIR = os.path.join(os.path.dirname(os.path.abspath(config.__file__)), "data")
_HAS_REAL = os.path.exists(os.path.join(_REAL_DIR, "categories.p"))

pytestmark = pytest.mark.skipif(not _HAS_REAL, reason="real pickle export not present in web-interface/data/")


def _load():
    return taxonomy._load_real(_REAL_DIR, config.FACULTY_CATEGORY_ID)


def test_real_loader_shape():
    offerings, _dom, _spec, years, stats = _load()
    assert len(offerings) >= 500
    assert {o["ciclu"] for o in offerings} == {"L", "M", "P"}
    assert stats["unresolved"] < 5  # only genuine Moodle mis-filings should fail to resolve
    assert years  # at least one academic year derived from the fullnames


def test_real_loader_no_curs_collisions():
    # guards the truncation bug fixed in _curs_id: one logical curs == one name
    offerings, *_ = _load()
    names_per_curs = {}
    for o in offerings:
        names_per_curs.setdefault(o["curs"], set()).add(o["denumire"])
    collisions = {k: sorted(v) for k, v in names_per_curs.items() if len(v) > 1}
    assert not collisions, f"curs ids merging different names: {list(collisions)[:3]}"


def test_real_loader_domains_have_labels():
    offerings, dom_labels, _spec, _years, _stats = _load()
    used = {o["domeniu"] for o in offerings}
    assert used <= set(dom_labels)  # every domeniu code carries a harvested label
    assert "CTI" in dom_labels
