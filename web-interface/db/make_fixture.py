#!/usr/bin/env python3
"""Coleg A: starting point for a local dev fixture.

Builds a small SQLite DB with the same schema as PR #3 (init.sql) and a
handful of fabricated rows, so queries.py can be developed and tested
before PR #3 merges upstream and a real moodle_analytics.db exists.

Run: python3 db/make_fixture.py  ->  writes db/fixture.db
"""
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
SCHEMA = HERE / "init.sql"
OUT = HERE / "fixture.db"


def main():
    if OUT.exists():
        OUT.unlink()
    conn = sqlite3.connect(OUT)
    conn.executescript(SCHEMA.read_text())

    # TODO(Coleg A): replace with enough fabricated rows to exercise every
    # query in queries.py (a few courses, a titular + assistants each,
    # enough feedback_responses to hit the deck's selection thresholds:
    # curs >=7% & >=3 fb; titular avg >=7% & >=15 fb; asistent >=10 fb).
    conn.execute(
        "INSERT INTO categories (category_id, name, parent_id, path, depth, sortorder) "
        "VALUES (1, 'ACS', NULL, '/1', 1, 1)"
    )
    conn.execute(
        "INSERT INTO courses (course_id, shortname, fullname, category_id) "
        "VALUES (1, '03-ACS-L-CTI-A1-S1-LS1E-CA', 'Programarea Calculatoarelor', 1)"
    )
    conn.execute(
        "INSERT INTO feedback_instances (instance_id, course_id, name) "
        "VALUES (1, 1, 'Feedback semestrial')"
    )
    conn.execute(
        "INSERT INTO feedback_responses (attempt_id, instance_id, prof_name, eval_overall) "
        "VALUES (1, 1, 'Popescu Ion', 5)"
    )

    conn.commit()
    conn.close()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
