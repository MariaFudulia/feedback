import os

# Path to the real DB once Coleg A wires queries.py to it. Not used by mocks.py.
DB_PATH = os.environ.get("FEEDBACK_DB_PATH", "db/fixture.db")
