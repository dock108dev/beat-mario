from __future__ import annotations

import hashlib
import http.client
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlencode

import pytest
import yaml

from smb3_agent.route_patch import (
    PATCH_SCHEMA_VERSION,
    RoutePatchError,
    _remove_worktree,
    compare_route_patch,
    import_route_patch,
    patch_summary_for_issue,
    prepare_route_patch,
    preview_route_patch,
    promote_route_patch,
    review_route_patch,
    rollback_route_patch,
    validate_route_patch,
)
from smb3_agent.lab_ui import _new_lab_ui_server, _route_patch_panel, run_patch_ui_action


def test_corrupt_patch_record_is_skipped_with_actionable_warning(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    repo, _, _ = _patch_fixture(tmp_path)
    corrupt = repo / "artifacts/route-patches/corrupt-record/contract.yaml"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_text("operations: [unterminated", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="smb3_agent.route_patch"):
        summary = patch_summary_for_issue("missing-issue", repo_root=repo)

    assert summary is None
    assert "route_patch_record_skipped" in caplog.text
    assert str(corrupt) in caplog.text


def test_route_lab_patch_validation_ignores_injected_game_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    expected = object()

    def fake_validate_route_patch(patch_id: str, **kwargs: object) -> object:
        captured.update({"patch_id": patch_id, **kwargs})
        return expected

    monkeypatch.delenv("SMB3_GAME_FILE", raising=False)
    monkeypatch.setattr("smb3_agent.lab_ui.validate_route_patch", fake_validate_route_patch)

    result = run_patch_ui_action(
        {
            "action": ["validate"],
            "patch_id": ["fixture-patch-001"],
            "game_file": ["/tmp/browser-controlled.nes"],
        },
        repo_root=tmp_path,
    )

    assert result is expected
    assert captured["patch_id"] == "fixture-patch-001"
    assert captured["game_path"] is None


def test_worktree_cleanup_refuses_current_directory(tmp_path: Path) -> None:
    repo, _, _ = _patch_fixture(tmp_path)
    patch_dir = repo / "artifacts/route-patches/fixture-patch-001"

    with pytest.raises(RoutePatchError, match="unsafe worktree cleanup target"):
        _remove_worktree(repo, Path("."), patch_dir=patch_dir)


def test_disposable_patch_executes_candidate_promotes_and_rolls_back(tmp_path: Path) -> None:
    repo, patch_path, original = _patch_fixture(tmp_path)

    imported = import_route_patch(patch_path, repo_root=repo)
    preview = preview_route_patch(imported.patch_id, repo_root=repo)
    assert preview.status == "imported"
    assert "-    return 'parent'" in preview.details["exact_diff"]
    assert "+    return 'candidate'" in preview.details["exact_diff"]
    assert (repo / "src/fixture_behavior.py").read_bytes() == original

    review_route_patch(imported.patch_id, repo_root=repo)
    prepared = prepare_route_patch(imported.patch_id, repo_root=repo)
    candidate_path = Path(prepared.details["candidate_path"])
    assert candidate_path != repo
    assert "candidate" in (candidate_path / "src/fixture_behavior.py").read_text()
    assert (repo / "src/fixture_behavior.py").read_bytes() == original

    validated = validate_route_patch(imported.patch_id, repo_root=repo)
    validation = yaml.safe_load(validated.artifact_path.read_text())
    assert validation["parent_outcome"]["passed"] is False
    assert validation["candidate_outcome"]["passed"] is True
    assert validation["candidate_results"][0]["cwd"] == str(candidate_path)
    assert validation["candidate_results"][0]["argv"] == ["bash", "scripts/validate_phase0.sh"]

    comparison = compare_route_patch(imported.patch_id, repo_root=repo)
    assert comparison.details["promotion_recommended"] is True
    promoted = promote_route_patch(
        imported.patch_id,
        confirm_patch_id=imported.patch_id,
        repo_root=repo,
    )
    assert "candidate" in (repo / "src/fixture_behavior.py").read_text()
    assert promoted.details["candidate_worktree_removed"] is True
    assert yaml.safe_load(promoted.artifact_path.read_text())["automatic_push"] is False

    rolled_back = rollback_route_patch(
        imported.patch_id,
        confirm_patch_id=imported.patch_id,
        reason="fixture acceptance proof",
        repo_root=repo,
    )
    assert rolled_back.status == "rolled_back"
    assert (repo / "src/fixture_behavior.py").read_bytes() == original
    history = yaml.safe_load((rolled_back.patch_dir / "state.yaml").read_text())["history"]
    assert [event["to"] for event in history] == [
        "imported",
        "reviewed",
        "prepared",
        "applied_to_candidate",
        "validated",
        "promoted",
        "rolled_back",
    ]


def test_candidate_validation_refuses_removed_patch_instead_of_running_parent(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    patch_id = import_route_patch(patch_path, repo_root=repo).patch_id
    review_route_patch(patch_id, repo_root=repo)
    prepared = prepare_route_patch(patch_id, repo_root=repo)
    candidate_path = Path(prepared.details["candidate_path"])
    (candidate_path / "src/fixture_behavior.py").write_text(
        "def behavior():\n    return 'parent'\n", encoding="utf-8"
    )

    with pytest.raises(RoutePatchError, match="Candidate contains unreviewed or missing"):
        validate_route_patch(patch_id, repo_root=repo)


def test_candidate_record_cannot_redirect_validation_or_cleanup(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    patch_id = import_route_patch(patch_path, repo_root=repo).patch_id
    review_route_patch(patch_id, repo_root=repo)
    prepared = prepare_route_patch(patch_id, repo_root=repo)
    candidate_record = prepared.artifact_path
    candidate = yaml.safe_load(candidate_record.read_text())
    candidate["candidate_path"] = str(repo)
    candidate_record.write_text(yaml.safe_dump(candidate, sort_keys=False), encoding="utf-8")

    with pytest.raises(RoutePatchError, match="unexpected worktree path"):
        validate_route_patch(patch_id, repo_root=repo)
    assert repo.is_dir()


def test_validation_record_cannot_redirect_output_hashing(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    patch_id = _validated_patch(repo, patch_path)
    compare_route_patch(patch_id, repo_root=repo)
    patch_dir = repo / "artifacts/route-patches" / patch_id
    validation_path = patch_dir / "validation.yaml"
    validation = yaml.safe_load(validation_path.read_text())
    validation["output_artifact_sha256"] = {"../../outside.txt": "0" * 64}
    validation_path.write_text(yaml.safe_dump(validation, sort_keys=False), encoding="utf-8")
    state_path = patch_dir / "state.yaml"
    state = yaml.safe_load(state_path.read_text())
    state["validation_record_sha256"] = _sha(validation_path.read_bytes())
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")

    with pytest.raises(RoutePatchError, match="Path traversal"):
        promote_route_patch(patch_id, confirm_patch_id=patch_id, repo_root=repo)


def test_validation_rejects_substitute_python_executable(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    patch_id = import_route_patch(patch_path, repo_root=repo).patch_id
    review_route_patch(patch_id, repo_root=repo)
    prepare_route_patch(patch_id, repo_root=repo)

    with pytest.raises(RoutePatchError, match="current Python executable"):
        validate_route_patch(patch_id, repo_root=repo, python_executable=Path("/bin/sh"))


def test_rollback_rejects_tampered_inverse_paths(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    patch_id = _validated_patch(repo, patch_path)
    compare_route_patch(patch_id, repo_root=repo)
    promote_route_patch(patch_id, confirm_patch_id=patch_id, repo_root=repo)
    inverse_path = repo / "artifacts/route-patches" / patch_id / "inverse-patch.yaml"
    inverse = yaml.safe_load(inverse_path.read_text())
    inverse["operations"][0]["path"] = "../outside.py"
    inverse_path.write_text(yaml.safe_dump(inverse, sort_keys=False), encoding="utf-8")

    with pytest.raises(RoutePatchError, match="does not match the reviewed contract"):
        rollback_route_patch(
            patch_id,
            confirm_patch_id=patch_id,
            reason="tampered inverse must fail closed",
            repo_root=repo,
        )


def test_import_rejects_symlinked_patch_document_and_external_artifact_root(
    tmp_path: Path,
) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    linked_patch = repo / "artifacts/intake/linked-patch.yaml"
    linked_patch.symlink_to(patch_path)
    with pytest.raises(RoutePatchError, match="must not be a symlink"):
        import_route_patch(linked_patch, repo_root=repo)
    external_patch = tmp_path / "external-patch.yaml"
    external_patch.write_bytes(patch_path.read_bytes())
    with pytest.raises(RoutePatchError, match="patch document escapes"):
        import_route_patch(external_patch, repo_root=repo)
    with pytest.raises(RoutePatchError, match="inside the repository"):
        import_route_patch(patch_path, repo_root=repo, artifacts_root=tmp_path / "outside")


def test_unreviewed_patch_cannot_prepare_or_promote(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    patch_id = import_route_patch(patch_path, repo_root=repo).patch_id

    with pytest.raises(RoutePatchError, match="must be reviewed"):
        prepare_route_patch(patch_id, repo_root=repo)
    with pytest.raises(RoutePatchError, match="must be validated"):
        promote_route_patch(patch_id, confirm_patch_id=patch_id, repo_root=repo)


def test_reviewed_route_lab_issue_normalizes_without_codex_task_packet(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    raw = yaml.safe_load(patch_path.read_text())
    raw["source"] = {
        "kind": "route_lab_issue",
        "session_id": "fixture-session",
        "issue_id": "fixture-issue",
        "note_ids": ["fixture-note"],
    }
    patch_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    imported = import_route_patch(patch_path, repo_root=repo)
    reviewed = review_route_patch(imported.patch_id, repo_root=repo)
    contract = yaml.safe_load((reviewed.patch_dir / "contract.yaml").read_text())

    assert contract["source"]["kind"] == "route_lab_issue"
    assert contract["source"]["task_packet"] is None
    assert reviewed.details["validation_profile"] == "canonical_phase"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda raw, repo: raw.update(repository_base_commit="0" * 40), "Stale base commit"),
        (
            lambda raw, repo: raw["operations"][0].update(preimage_sha256="0" * 64),
            "Stale preimage",
        ),
        (lambda raw, repo: raw["operations"][0].update(path="/tmp/evil.py"), "Absolute paths"),
        (lambda raw, repo: raw["operations"][0].update(path="../evil.py"), "Path traversal"),
        (
            lambda raw, repo: raw["operations"][0].update(path="src/undeclared.py"),
            "absent from allowed_files",
        ),
        (
            lambda raw, repo: raw["operations"][0].update(path="artifacts/report.log"),
            "forbidden",
        ),
        (lambda raw, repo: raw.update(validation_command="rm -rf ."), "forbidden"),
        (
            lambda raw, repo: raw["operations"][0].update(kind="unified_diff", patch="@@ -1 +1 @@"),
            "must contain exactly",
        ),
        (lambda raw, repo: raw.update(validated=True), "forbidden"),
    ],
)
def test_import_rejects_unsafe_or_self_authorizing_patch(
    tmp_path: Path, mutate, message: str
) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    raw = yaml.safe_load(patch_path.read_text())
    mutate(raw, repo)
    patch_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(RoutePatchError, match=message):
        import_route_patch(patch_path, repo_root=repo)
    assert not (repo / "artifacts/route-patches/fixture-patch-001").exists()


def test_import_rejects_symlink_escape(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("safe = False\n", encoding="utf-8")
    link = repo / "src/escape.py"
    link.symlink_to(outside)
    raw = yaml.safe_load(patch_path.read_text())
    raw["allowed_files"] = ["src/escape.py"]
    operation = raw["operations"][0]
    operation["path"] = "src/escape.py"
    operation["preimage_sha256"] = _sha(outside.read_bytes())
    operation["expected_postimage_sha256"] = _sha(b"safe = True\n")
    operation["content"] = "safe = True\n"
    patch_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(RoutePatchError, match="Symlink"):
        import_route_patch(patch_path, repo_root=repo)


def test_import_rejects_malformed_encoding_overlaps_and_already_applied_operations(
    tmp_path: Path,
) -> None:
    repo, patch_path, original = _patch_fixture(tmp_path)
    patch_path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(RoutePatchError, match="malformed UTF-8"):
        import_route_patch(patch_path, repo_root=repo)

    repo2, patch_path2, _ = _patch_fixture(tmp_path / "overlap")
    raw = yaml.safe_load(patch_path2.read_text())
    raw["operations"].append(dict(raw["operations"][0]))
    patch_path2.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(RoutePatchError, match="Overlapping or duplicate"):
        import_route_patch(patch_path2, repo_root=repo2)

    repo3, patch_path3, _ = _patch_fixture(tmp_path / "applied")
    raw = yaml.safe_load(patch_path3.read_text())
    unchanged_hash = _sha(original)
    raw["operations"][0]["content"] = original.decode("utf-8")
    raw["operations"][0]["expected_postimage_sha256"] = unchanged_hash
    raw["expected_postimage_sha256"]["src/fixture_behavior.py"] = unchanged_hash
    patch_path3.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(RoutePatchError, match="already applied or has no effect"):
        import_route_patch(patch_path3, repo_root=repo3)


def test_review_rejects_file_absent_from_task_packet_allowlist(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    patch_id = import_route_patch(patch_path, repo_root=repo).patch_id
    task_path = repo / "artifacts/sessions/fixture-session/codex_tasks/fixture-issue.yaml"
    task = yaml.safe_load(task_path.read_text())
    task["inputs"]["relevant_files"] = ["tests/fixture.txt"]
    (repo / "tests/fixture.txt").write_text("fixture\n", encoding="utf-8")
    task_path.write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")

    with pytest.raises(RoutePatchError, match="absent from reviewed allowlist"):
        review_route_patch(patch_id, repo_root=repo)


def test_diff_change_dirty_target_duplicate_promotion_and_conflicting_rollback_are_refused(
    tmp_path: Path,
) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path)
    patch_id = _validated_patch(repo, patch_path)
    (repo / "artifacts/route-patches" / patch_id / "candidate.diff").write_text(
        "tampered\n", encoding="utf-8"
    )
    with pytest.raises(RoutePatchError, match="diff artifact changed"):
        compare_route_patch(patch_id, repo_root=repo)

    # Restore the disposable fixture and validate it again for promotion guards.
    repo2, patch_path2, _ = _patch_fixture(tmp_path / "second")
    patch_id2 = _validated_patch(repo2, patch_path2)
    compare_route_patch(patch_id2, repo_root=repo2)
    (repo2 / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(RoutePatchError, match="working tree is not clean"):
        promote_route_patch(patch_id2, confirm_patch_id=patch_id2, repo_root=repo2)
    (repo2 / "untracked.txt").unlink()
    promote_route_patch(patch_id2, confirm_patch_id=patch_id2, repo_root=repo2)
    with pytest.raises(RoutePatchError, match="must be validated"):
        promote_route_patch(patch_id2, confirm_patch_id=patch_id2, repo_root=repo2)
    (repo2 / "src/fixture_behavior.py").write_text(
        "def behavior():\n    return 'later edit'\n", encoding="utf-8"
    )
    with pytest.raises(RoutePatchError, match="later conflicting edits"):
        rollback_route_patch(
            patch_id2,
            confirm_patch_id=patch_id2,
            reason="must not overwrite later work",
            repo_root=repo2,
        )


def test_partial_promotion_failure_restores_all_files_atomically(tmp_path: Path) -> None:
    repo, patch_path, original = _patch_fixture(tmp_path, two_files=True)
    patch_id = _validated_patch(repo, patch_path)
    compare_route_patch(patch_id, repo_root=repo)
    second_original = (repo / "src/fixture_second.py").read_bytes()

    with pytest.raises(RoutePatchError, match="injected partial-write failure"):
        promote_route_patch(
            patch_id,
            confirm_patch_id=patch_id,
            repo_root=repo,
            _fail_after_writes=1,
        )
    assert (repo / "src/fixture_behavior.py").read_bytes() == original
    assert (repo / "src/fixture_second.py").read_bytes() == second_original
    failure = yaml.safe_load(
        (repo / "artifacts/route-patches" / patch_id / "promotion-failure.yaml").read_text()
    )
    assert failure["restored_atomically"] is True
    assert failure["exception"]["type"] == "OSError"
    assert "injected partial-write failure" in failure["exception"]["traceback"]


def test_documentation_only_patch_is_validatable_but_not_promotable(tmp_path: Path) -> None:
    repo, patch_path, _ = _patch_fixture(tmp_path, changed_path="docs/fixture.md")
    patch_id = import_route_patch(patch_path, repo_root=repo).patch_id
    review_route_patch(patch_id, repo_root=repo)
    prepare_route_patch(patch_id, repo_root=repo)
    validation = validate_route_patch(patch_id, repo_root=repo)
    assert validation.details["execution_proof"] is False
    comparison = compare_route_patch(patch_id, repo_root=repo)
    assert comparison.details["promotion_recommended"] is False
    with pytest.raises(RoutePatchError, match="comparison does not recommend"):
        promote_route_patch(patch_id, confirm_patch_id=patch_id, repo_root=repo)


def test_cli_and_route_lab_http_actions_share_patch_backend_and_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo, patch_path, original = _patch_fixture(tmp_path)
    project_src = Path(__file__).resolve().parents[1] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_src)
    imported = subprocess.run(
        [sys.executable, "-m", "smb3_agent", "lab", "patch", "import", str(patch_path)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "status=imported" in imported.stdout
    patch_id = "fixture-patch-001"
    patch_dir = repo / "artifacts/route-patches" / patch_id

    monkeypatch.chdir(repo)
    server = _new_lab_ui_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        body = urlencode(
            {
                "action": "review",
                "patch_id": patch_id,
                "issue_id": "fixture-issue",
                "return_location": "fixture-location",
                "return_goal": "world_8_double_whistle",
                "csrf_token": getattr(server, "csrf_token"),
            }
        )
        connection.request(
            "POST",
            "/patch-action",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        response_body = response.read().decode("utf-8")
        assert response.status == 303, response_body
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert yaml.safe_load((patch_dir / "state.yaml").read_text())["status"] == "reviewed"
    prepared = run_patch_ui_action(
        {"action": ["prepare"], "patch_id": [patch_id]}, repo_root=repo
    )
    assert prepared.status == "applied_to_candidate"
    validated = run_patch_ui_action(
        {"action": ["validate"], "patch_id": [patch_id]}, repo_root=repo
    )
    assert validated.status == "validated"
    run_patch_ui_action({"action": ["compare"], "patch_id": [patch_id]}, repo_root=repo)

    summary = preview_route_patch(patch_id, repo_root=repo).details
    summary.update(
        {
            "patch_id": patch_id,
            "status": "validated",
            "review_state": "reviewed",
            "validation_result": True,
        }
    )
    html = _route_patch_panel(
        {
            "id": "fixture-issue",
            "task_packet": "artifacts/sessions/fixture-session/codex_tasks/fixture-issue.yaml",
            "route_patch": summary,
        },
        "fixture-location",
    )
    assert f'data-patch-id="{patch_id}"' in html
    assert "Exact diff preview" in html
    assert "src/fixture_behavior.py" in html
    assert "Review" in html and "Validate" in html and "Compare" in html
    assert "Promote" in html and "Rollback" in html
    assert f"Type {patch_id} to promote" in html

    with pytest.raises(RoutePatchError, match="confirmation"):
        run_patch_ui_action(
            {
                "action": ["promote"],
                "patch_id": [patch_id],
                "confirmation": ["wrong-patch"],
            },
            repo_root=repo,
        )
    run_patch_ui_action(
        {
            "action": ["promote"],
            "patch_id": [patch_id],
            "confirmation": [patch_id],
        },
        repo_root=repo,
    )
    assert b"candidate" in (repo / "src/fixture_behavior.py").read_bytes()
    run_patch_ui_action(
        {
            "action": ["rollback"],
            "patch_id": [patch_id],
            "confirmation": [patch_id],
            "reason": ["Route Lab parity proof"],
        },
        repo_root=repo,
    )
    assert (repo / "src/fixture_behavior.py").read_bytes() == original
    actors = {event["actor"] for event in yaml.safe_load((patch_dir / "state.yaml").read_text())["history"]}
    assert actors == {"cli", "route_lab"}


def _validated_patch(repo: Path, patch_path: Path) -> str:
    patch_id = import_route_patch(patch_path, repo_root=repo).patch_id
    review_route_patch(patch_id, repo_root=repo)
    prepare_route_patch(patch_id, repo_root=repo)
    validate_route_patch(patch_id, repo_root=repo)
    return patch_id


def _patch_fixture(
    tmp_path: Path,
    *,
    two_files: bool = False,
    changed_path: str = "src/fixture_behavior.py",
) -> tuple[Path, Path, bytes]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "scripts").mkdir()
    (repo / "docs").mkdir()
    (repo / "tests").mkdir()
    (repo / "src/undeclared.py").write_text("UNDECLARED = True\n", encoding="utf-8")
    target = repo / changed_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if changed_path.endswith(".md"):
        original = b"# Parent documentation\n"
        replacement = b"# Candidate documentation\n"
    else:
        original = b"def behavior():\n    return 'parent'\n"
        replacement = b"def behavior():\n    return 'candidate'\n"
    target.write_bytes(original)
    (repo / "scripts/validate_phase0.sh").write_text(
        "#!/bin/sh\nset -eu\n"
        '"${PYTHON}" -c "from fixture_behavior import behavior; assert behavior() == \'candidate\'"\n',
        encoding="utf-8",
    )
    operations = [_operation(changed_path, original, replacement)]
    allowed_files = [changed_path]
    if two_files:
        second = repo / "src/fixture_second.py"
        second_before = b"VALUE = 'parent'\n"
        second_after = b"VALUE = 'candidate'\n"
        second.write_bytes(second_before)
        operations.append(_operation("src/fixture_second.py", second_before, second_after))
        allowed_files.append("src/fixture_second.py")

    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Beat Mario Test")
    _git(repo, "config", "user.email", "beat-mario@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "fixture baseline")
    base_commit = _git_output(repo, "rev-parse", "HEAD").strip()

    session_dir = repo / "artifacts/sessions/fixture-session"
    (session_dir / "codex_tasks").mkdir(parents=True)
    (session_dir / "session.yaml").write_text(
        yaml.safe_dump({"session_id": "fixture-session"}), encoding="utf-8"
    )
    (session_dir / "review.yaml").write_text(
        yaml.safe_dump({"session_id": "fixture-session", "result": "needs_route_hardening"}),
        encoding="utf-8",
    )
    (session_dir / "notes.yaml").write_text(
        yaml.safe_dump({"notes": [{"id": "fixture-note", "text": "parent behavior is unsafe"}]}),
        encoding="utf-8",
    )
    issue = {
        "id": "fixture-issue",
        "status": "open",
        "actionable": True,
        "source_notes": ["fixture-note"],
        "relevant_files": allowed_files,
    }
    (session_dir / "issues.yaml").write_text(
        yaml.safe_dump({"session_id": "fixture-session", "issues": [issue]}), encoding="utf-8"
    )
    task_rel = "artifacts/sessions/fixture-session/codex_tasks/fixture-issue.yaml"
    task = {
        "task_id": "fixture-task",
        "session_id": "fixture-session",
        "issue_id": "fixture-issue",
        "inputs": {"relevant_files": allowed_files},
        "expected_output": {"artifact": PATCH_SCHEMA_VERSION},
    }
    (repo / task_rel).write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")

    patch = {
        "schema_version": PATCH_SCHEMA_VERSION,
        "patch_id": "fixture-patch-001",
        "variant_id": "fixture-variant-001",
        "source": {
            "kind": "codex_task",
            "session_id": "fixture-session",
            "issue_id": "fixture-issue",
            "note_ids": ["fixture-note"],
            "task_id": "fixture-task",
            "task_packet": task_rel,
        },
        "parent_variant": "fixture-parent",
        "repository_base_commit": base_commit,
        "allowed_files": allowed_files,
        "preimage_sha256": {item["path"]: item["preimage_sha256"] for item in operations},
        "operations": operations,
        "expected_postimage_sha256": {
            item["path"]: item["expected_postimage_sha256"] for item in operations
        },
        "summary": "Change disposable fixture behavior for isolated candidate proof.",
        "rollback_description": "Restore the exact recorded parent bytes.",
        "lifecycle": {"status": "imported"},
        "timestamps": {"created_at": "2026-08-10T00:00:00+00:00"},
        "provenance": {"producer": "rank-33-test-fixture", "owner_selected": True},
    }
    patch_path = repo / "artifacts/intake/fixture-patch.yaml"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(yaml.safe_dump(patch, sort_keys=False), encoding="utf-8")
    return repo, patch_path, original


def _operation(path: str, before: bytes, after: bytes) -> dict[str, str]:
    return {
        "kind": "replace_text",
        "path": path,
        "preimage_sha256": _sha(before),
        "expected_postimage_sha256": _sha(after),
        "content": after.decode("utf-8"),
    }


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _git_output(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
