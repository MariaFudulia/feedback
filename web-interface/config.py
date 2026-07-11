import os

_HERE = os.path.dirname(os.path.abspath(__file__))

# Path to the real DB once queries.py is wired to it. Not used by mocks.py.
DB_PATH = os.environ.get("FEEDBACK_DB_PATH", os.path.join(_HERE, "db", "fixture.db"))

# Directory holding the retrieve-feedback pickle export (categories.p, courses.p,
# courses4categories.p, feedbacks.p). Gitignored -- real institutional data.
# taxonomy.py reads it when present, else falls back to a synthetic dataset.
FEEDBACK_DATA_DIR = os.environ.get("FEEDBACK_DATA_DIR", os.path.join(_HERE, "data"))

# Moodle category id of the faculty to scope to (ACS = 7).
FACULTY_CATEGORY_ID = int(os.environ.get("FEEDBACK_FACULTY_CAT", "7"))

# Whether the loaded feedback content is fabricated -- this drives the 'date
# demonstrative' badge. Deliberately fails closed: content counts as REAL only when this
# is explicitly set to "0". Leave it unset for a generated (generate-feedback) export or
# for anything whose provenance you are not certain of; the badge stays on and the app
# keeps telling the truth about its own numbers.
CONTENT_SYNTHETIC = os.environ.get("FEEDBACK_CONTENT_SYNTHETIC")

# Flask session signing key. Dev default is fine locally; set FEEDBACK_SECRET_KEY
# in any shared/deployed environment.
SECRET_KEY = os.environ.get("FEEDBACK_SECRET_KEY", "dev-feedback-upb-change-me")
