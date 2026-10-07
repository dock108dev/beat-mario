"""Delivery tooling with synthetic packages, signatures and calibration evidence."""

import hashlib
import json
import plistlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from smb3_agent import release_resources

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STABLE_REQUIREMENT = (
    'identifier "local.gamecompanion.privatebeta" and anchor apple generic'
)


def load_script(name, *, optimize=0):
    path = REPOSITORY_ROOT / "scripts" / name
    module = ModuleType(path.stem)
    module.__file__ = str(path)
    exec(
        compile(path.read_text(), str(path), "exec", optimize=optimize), module.__dict__
    )
    return module


@pytest.mark.parametrize("name", ["build_private_beta.py", "install_private_beta.py"])
def test_delivery_tool_import_does_not_parse_arguments_or_run_commands(
    name, monkeypatch
):
    monkeypatch.setattr(sys, "argv", [name, "--unknown-import-argument"])

    def refused(*args, **kwargs):
        pytest.fail("Import must not start external operations")

    monkeypatch.setattr(subprocess, "run", refused)
    module = load_script(name)
    assert callable(module.main)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--sign-identity", "-"],
        ["--sign-identity", "synthetic", "--version", "../invalid"],
        ["--sign-identity", "synthetic", "--build", "not-numeric"],
    ],
)
def test_builder_rejects_invalid_arguments_before_staging(arguments, monkeypatch):
    module = load_script("build_private_beta.py")

    def refused(*args, **kwargs):
        pytest.fail("Invalid arguments must not stage resources or start a build")

    monkeypatch.setattr(module, "stage_resources", refused)
    monkeypatch.setattr(subprocess, "run", refused)
    with pytest.raises(SystemExit) as exc:
        module.main(arguments)
    assert exc.value.code == 2


@pytest.fixture(params=[0, 2], ids=["normal-python", "optimized-python"])
def installation(tmp_path, monkeypatch, request):
    module = load_script("install_private_beta.py", optimize=request.param)
    home = tmp_path / "synthetic-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    package = tmp_path / "candidate"
    package.mkdir()
    (package / "build-manifest.json").write_text(
        json.dumps({"version": "synthetic-candidate", "build": "42"})
    )

    def app(path, content):
        (path / "Contents").mkdir(parents=True)
        (path / "Contents/Info.plist").write_bytes(
            plistlib.dumps({"CFBundleIdentifier": "local.gamecompanion.privatebeta"})
        )
        (path / "Contents/payload").write_text(content)

    source = package / "Game Companion.app"
    destination = home / "Applications/Game Companion.app"
    app(source, "new synthetic payload")
    app(destination, "old synthetic payload")

    def command(arguments, **kwargs):
        if arguments[0] == "pgrep":
            return SimpleNamespace(returncode=1)
        assert arguments[0] == "codesign"
        return SimpleNamespace(
            returncode=0, stdout="", stderr=f"designated => {STABLE_REQUIREMENT}\n"
        )

    monkeypatch.setattr(subprocess, "run", command)
    return SimpleNamespace(module=module, package=package, destination=destination)


def test_install_archives_previous_app_and_records_separate_permission_status(
    installation,
):
    context = installation
    context.module.main([str(context.package)])
    receipt = json.loads((context.package / "installation-receipt.json").read_text())
    assert (
        context.destination / "Contents/payload"
    ).read_text() == "new synthetic payload"
    assert (
        Path(receipt["previous_app"]) / "Contents/payload"
    ).read_text() == "old synthetic payload"
    assert receipt["designated_requirement"] == STABLE_REQUIREMENT
    assert receipt["data_modified"] is False
    assert receipt["permission_access_verified"] is False
    assert (context.package / "Game Companion.app/Contents/payload").is_file()


def test_staged_identity_mismatch_refuses_before_archiving_even_when_optimized(
    installation, monkeypatch
):
    context = installation
    verify = context.module.verify

    def mismatched(app):
        return (
            "different designated requirement" if "update-" in app.name else verify(app)
        )

    monkeypatch.setattr(context.module, "verify", mismatched)
    with pytest.raises(RuntimeError, match="Staged identity differs"):
        context.module.main([str(context.package)])
    assert (
        context.destination / "Contents/payload"
    ).read_text() == "old synthetic payload"
    staged = context.destination.parent / "Game Companion.update-42.app"
    assert (staged / "Contents/payload").read_text() == "new synthetic payload"
    assert not (context.destination.parent / "Game Companion retained updates").exists()
    assert not (context.package / "installation-receipt.json").exists()


def test_failed_final_move_restores_previous_app_and_retains_staged_copy(
    installation, monkeypatch
):
    context = installation
    rename = Path.rename

    def fail_staged_move(path, target):
        if path.name == "Game Companion.update-42.app":
            raise OSError("Synthetic rename failure")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_staged_move)
    with pytest.raises(OSError, match="Synthetic rename failure"):
        context.module.main([str(context.package)])
    assert (
        context.destination / "Contents/payload"
    ).read_text() == "old synthetic payload"
    assert (context.destination.parent / "Game Companion.update-42.app").is_dir()
    assert not (context.package / "installation-receipt.json").exists()


@pytest.fixture
def calibration_source(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    for name in release_resources.LUA:
        path = root / "scripts" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("-- synthetic controller resource\n")
    contract = root / "data/companion/local-candidate.yaml"
    contract.parent.mkdir(parents=True)
    contract.write_text("schema: synthetic\n")
    tracked = "data/companion/local-candidate.yaml\0"
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **kw: tracked)

    def profile(relative, evidence_relative):
        evidence = root / evidence_relative
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_bytes(b"synthetic calibration evidence")
        digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
        value = {
            "evidence_hashes": {str(evidence): digest},
            "nested": [{"image": str(evidence), "known_zero": 0, "unknown": None}],
        }
        manifest = root / relative
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(value))
        return evidence

    day2 = profile(
        release_resources.DAY2_PROFILE, "artifacts/b3-engineering/synthetic/scene.log"
    )
    view_manifest = "artifacts/gc-delivery/ordinary-session/20261006-recovery/view-feature-calibration/profile.json"
    view = profile(
        view_manifest,
        "artifacts/gc-delivery/ordinary-session/20261006-recovery/synthetic/scene.png",
    )
    return SimpleNamespace(root=root, day2=day2, view=view, view_manifest=view_manifest)


def test_profiles_relocate_independently_with_inventory_and_originals_preserved(
    calibration_source, tmp_path
):
    context = calibration_source
    before = {path: path.read_bytes() for path in (context.day2, context.view)}
    destination = tmp_path / "resources"
    records = release_resources.stage_resources(context.root, destination)
    for directory, suffix in (("day2", ".log"), ("view-settings", ".png")):
        profile = json.loads(
            (destination / "data/calibration" / directory / "profile.json").read_text()
        )
        reference = f"gc-resource:data/calibration/{directory}/000{suffix}"
        assert list(profile["evidence_hashes"]) == [reference]
        assert profile["nested"] == [
            {"image": reference, "known_zero": 0, "unknown": None}
        ]
    assert {path: path.read_bytes() for path in before} == before
    for record in records:
        assert (
            hashlib.sha256((destination / record["path"]).read_bytes()).hexdigest()
            == record["sha256"]
        )


def test_display_profile_still_refuses_log_evidence(calibration_source, tmp_path):
    context = calibration_source
    manifest = context.root / context.view_manifest
    log = context.view.with_suffix(".log")
    log.write_bytes(context.view.read_bytes())
    manifest.write_text(
        json.dumps(
            {
                "evidence_hashes": {
                    str(log): hashlib.sha256(log.read_bytes()).hexdigest()
                }
            }
        )
    )
    with pytest.raises(ValueError, match="Visible display feature eligibility refused"):
        release_resources.stage_resources(context.root, tmp_path / "refused-resources")
