"""Build persistence failures use disposable SQLite files and a fake worker."""

import json
import sqlite3

import pytest

from smb3_agent.minecraft_build import BuildProject


REGION = {
    "bounds": {"min": dict(x=0, y=0, z=0), "max": dict(x=10, y=10, z=10)},
    "protected": [],
}
CELLS = [{"position": dict(x=x, y=1, z=1), "after": "stone"} for x in (1, 2)]


class Worker:
    session_id = "synthetic"
    revision = 0

    def __init__(self):
        self.blocks = {}
        self.damage = lambda rows: rows
        self.writes = 0

    def call(self, op, args, **kwargs):
        if op == "inspect_build":
            return self.damage(
                [
                    {"position": p, "state": self.blocks.get(tuple(p.values()), "air")}
                    for p in args["positions"]
                ]
            )
        self.writes += 1
        for cell in args["cells"]:
            self.blocks[tuple(cell["position"].values())] = cell["after"]
        return {"observed": "verified_build_batch"}


@pytest.fixture
def project(tmp_path):
    value = BuildProject(tmp_path, "synthetic", REGION, Worker())
    yield value
    value.close()


@pytest.mark.parametrize(
    "damage",
    [
        lambda rows: [],
        lambda rows: rows[:1],
        lambda rows: rows[::-1],
        lambda rows: rows + rows[:1],
        lambda rows: [rows[0], rows[0]],
        lambda rows: [{**row, "state": None} for row in rows],
        lambda rows: [{**row, "state": ""} for row in rows],
    ],
)
def test_bad_survey_does_not_publish_design(project, damage):
    project.bridge.damage = damage
    with pytest.raises(ValueError, match="inspection"):
        project.prepare(CELLS)
    assert project.revision == 0
    assert project.db.execute("SELECT COUNT(*) FROM designs").fetchone()[0] == 0
    assert project.bridge.writes == 0


def test_missing_recovery_observation_keeps_pending_intent(project):
    project.prepare(CELLS)

    def interrupt(point, uid):
        if point == "intent":
            raise RuntimeError("interrupted")

    project.run(fault=interrupt)
    project.bridge.damage = lambda rows: []
    assert project.run()["state"] == "needs_review"
    assert project.db.execute("SELECT status FROM units").fetchall() == [("pending",)]
    assert project.bridge.writes == 0
    project.bridge.damage = lambda rows: rows
    assert project.run()["state"] == "complete"
    assert project.bridge.writes == 1


def test_missing_final_survey_cannot_report_complete(project):
    project.prepare(CELLS)

    def lose_observation(point, uid):
        if point == "receipt":
            project.bridge.damage = lambda rows: []

    assert project.run(fault=lose_observation)["state"] == "needs_review"
    assert project.bridge.writes == 1


def test_failed_design_write_preserves_selected_revision_and_rolls_back(project):
    project.prepare(CELLS)
    project.db.execute(
        "CREATE TEMP TRIGGER fail_design BEFORE INSERT ON designs BEGIN SELECT RAISE(FAIL, 'disk failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="disk failure"):
        project.prepare(CELLS)
    assert project.revision == 1
    assert not project.db.in_transaction
    project.db.execute("DROP TRIGGER fail_design")
    assert project.prepare(CELLS)["revision"] == 2


def test_failed_receipt_rolls_back_and_reconciles_without_replay(project):
    project.prepare(CELLS)
    project.db.execute(
        "CREATE TEMP TRIGGER fail_receipt BEFORE UPDATE ON units BEGIN SELECT RAISE(FAIL, 'disk failure'); END"
    )
    assert project.run()["state"] == "needs_review"
    assert not project.db.in_transaction
    with sqlite3.connect(project.root / "project.sqlite") as reader:
        assert reader.execute("SELECT status FROM units").fetchall() == [("pending",)]
    project.db.execute("DROP TRIGGER fail_receipt")
    assert project.run()["state"] == "complete"
    assert project.bridge.writes == 1
    assert (
        len(json.loads(project.db.execute("SELECT cells FROM designs").fetchone()[0]))
        == 2
    )


def test_legacy_schema_upgrade_preserves_intent_and_reopens_idle(tmp_path):
    identity = json.dumps({"world": "synthetic", "region": REGION}, sort_keys=True)
    cells = json.dumps([{**cell, "before": "air"} for cell in CELLS])
    with sqlite3.connect(tmp_path / "project.sqlite") as db:
        db.executescript(
            "CREATE TABLE identity(id INTEGER PRIMARY KEY,value TEXT);"
            "CREATE TABLE designs(revision INTEGER PRIMARY KEY,cells TEXT);"
            "CREATE TABLE units(id INTEGER PRIMARY KEY,revision INTEGER,cells TEXT,status TEXT,elapsed REAL);"
            "CREATE TABLE terrain_stages(manifest INTEGER,ordinal INTEGER,digest TEXT,design_revision INTEGER,PRIMARY KEY(manifest,ordinal));"
        )
        db.execute("INSERT INTO identity VALUES(1,?)", (identity,))
        db.execute("INSERT INTO designs VALUES(1,?)", (cells,))
        db.execute("INSERT INTO units VALUES(1,1,?,'pending',NULL)", (cells,))
        db.execute("INSERT INTO terrain_stages VALUES(1,0,'saved',1)")
    worker = Worker()
    for _ in range(2):
        project = BuildProject(tmp_path, "synthetic", REGION, worker)
        try:
            assert project.state == "idle" and worker.writes == 0
            assert project.db.execute("SELECT * FROM terrain_stages").fetchall() == [
                (1, 0, "saved", 1, 0)
            ]
            assert project.db.execute(
                "SELECT cells,status,elapsed FROM units"
            ).fetchall() == [(cells, "pending", None)]
            assert project.summary()["units"] == [("pending", 1, None)]
        finally:
            project.close()


@pytest.mark.parametrize("operation", ["design", "receipt"])
def test_commit_failure_does_not_leak_into_next_operation(project, operation):
    project.prepare(CELLS)
    # A deferred foreign-key violation fails COMMIT, after the write succeeded.
    project.db.execute("PRAGMA foreign_keys=ON")
    project.db.executescript(
        "CREATE TABLE fault_parent(id INTEGER PRIMARY KEY);"
        "CREATE TABLE fault_child(parent INTEGER REFERENCES fault_parent(id) DEFERRABLE INITIALLY DEFERRED);"
    )
    target = "INSERT ON designs" if operation == "design" else "UPDATE ON units"
    project.db.execute(
        f"CREATE TEMP TRIGGER commit_fault AFTER {target} "
        "BEGIN INSERT INTO fault_child VALUES(99); END"
    )
    if operation == "design":
        with pytest.raises(sqlite3.IntegrityError):
            project.prepare(CELLS)
        assert project.revision == 1
        assert project.db.execute("SELECT COUNT(*) FROM designs").fetchone()[0] == 1
    else:
        assert project.run()["state"] == "needs_review"
        assert project.db.execute("SELECT status FROM units").fetchall() == [
            ("pending",)
        ]
    assert not project.db.in_transaction
    assert project.db.execute("SELECT COUNT(*) FROM fault_child").fetchone()[0] == 0
    project.db.execute("DROP TRIGGER commit_fault")
    assert project.run()["state"] == "complete"
    assert project.bridge.writes == 1
