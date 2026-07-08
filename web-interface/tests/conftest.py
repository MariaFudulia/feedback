"""Force the synthetic taxonomy fallback for the whole test session.

pytest imports conftest before any test module, so this sets FEEDBACK_DATA_DIR to
a path with no pickles *before* taxonomy is first imported -- the singleton loads
synthetic regardless of collection order. Without this, running test_real_data.py
(which loads the real export directly) before test_contract.py would leave the
singleton pointed at real data and fail the synthetic-dependent tests.

test_real_data.py is unaffected: it calls taxonomy._load_real(_REAL_DIR, ...)
directly, bypassing the singleton.
"""

import os

os.environ["FEEDBACK_DATA_DIR"] = "/tmp/feedback-no-such-data-dir"
