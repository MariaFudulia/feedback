-- Copied from PR #3 (lakalex:sql-support) — cs-pub-ro/feedback.
-- This is the schema the real moodle_analytics.db will have once PR #3 merges.
-- Coleg A: use this to build db/make_fixture.py (a small local DB to develop against
-- before PR #3 is merged upstream).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT,
    parent_id INTEGER,
    path TEXT,
    depth INTEGER,
    sortorder INTEGER,
    FOREIGN KEY (parent_id) REFERENCES categories(category_id) ON DELETE SET NULL );

CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);

CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY,
    shortname TEXT UNIQUE NOT NULL,
    fullname TEXT, startdate INTEGER,
    enddate INTEGER, category_id INTEGER,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) );

CREATE INDEX IF NOT EXISTS idx_courses_category ON courses(category_id);
CREATE INDEX IF NOT EXISTS idx_courses_shortname ON courses(shortname);

CREATE TABLE IF NOT EXISTS feedback_instances (
    instance_id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL,
    name TEXT,
    anonymous BOOLEAN DEFAULT 1,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) );

CREATE TABLE IF NOT EXISTS feedback_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER UNIQUE,
    instance_id INTEGER NOT NULL,
    prof_name TEXT,
    assist_name TEXT,
    eval_overall INTEGER,
    expected_grade INTEGER,
    load INTEGER,
    equipment INTEGER,
    part_percent INTEGER,
    prof_know INTEGER,
    prof_teach INTEGER,
    prof_interact INTEGER,
    prof_behave INTEGER,
    lecture_doc INTEGER,
    assist_know INTEGER,
    assist_teach INTEGER,
    assist_interact INTEGER,
    assist_behave INTEGER,
    lab_doc INTEGER,
    assign_time INTEGER,
    assign_diff INTEGER,
    assign_useful INTEGER,
    positive_text TEXT,
    negative_text TEXT,
    difficulty_text TEXT,
    other_text TEXT,
    FOREIGN KEY (instance_id) REFERENCES feedback_instances(instance_id) );

CREATE INDEX IF NOT EXISTS idx_resp_prof ON feedback_responses(prof_name);
CREATE INDEX IF NOT EXISTS idx_resp_assist ON feedback_responses(assist_name);
