from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path
import tomllib

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/ci.yml"
DEPENDABOT_PATH = REPOSITORY_ROOT / ".github/dependabot.yml"
GATE_PATH = REPOSITORY_ROOT / "scripts/validate_phase0.sh"
PYPROJECT_PATH = REPOSITORY_ROOT / "pyproject.toml"
CLI_PATH = REPOSITORY_ROOT / "src/smb3_agent/cli.py"
LAB_PATH = REPOSITORY_ROOT / "src/smb3_agent/lab.py"
COMMANDS_PATH = REPOSITORY_ROOT / "src/smb3_agent/commands.py"
CATALOG_PATH = REPOSITORY_ROOT / "src/smb3_agent/companion_catalog.py"
LAB_UI_PATH = REPOSITORY_ROOT / "src/smb3_agent/lab_ui.py"
EXPERIMENTAL_ADAPTERS_PATH = REPOSITORY_ROOT / "src/smb3_agent/experimental_adapters.py"
README_PATH = REPOSITORY_ROOT / "README.md"
RUNTIME_DOC_PATH = REPOSITORY_ROOT / "docs/runtime-and-configuration.md"
STARDEW_GUIDE_PATH = REPOSITORY_ROOT / "docs/stardew-operator-guide.md"
FINAL_CAMPAIGN_PATH = REPOSITORY_ROOT / "data/scenarios/final-campaign.yaml"
CAMPAIGN_ENTRY_SCHEMA_PATH = REPOSITORY_ROOT / "data/scenarios/campaign-entry-manifest-schema.json"
ROADMAP_PATH = REPOSITORY_ROOT / "docs/v2-roadmap.md"
CHECKOUT_PIN = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_PIN = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
SETUP_UV_PIN = "astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d"
DEPENDENCY_REVIEW_PIN = (
    "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294"
)
MACOS_MODULES = (
    "smb3_agent.backends.mednafen",
    "smb3_agent.probes.mednafen_probe",
    "smb3_agent.tasks.checkpoint_1_1",
    "smb3_agent.tasks.enter_1_1",
    "smb3_agent.tasks.load_checkpoint_1_1",
    "smb3_agent.tasks.run_1_1_script",
    "smb3_agent.tasks.start_game",
)
LEGACY_MEDNAFEN_RESULT_MODULES = (
    REPOSITORY_ROOT / "src/smb3_agent/probes/mednafen_probe.py",
    REPOSITORY_ROOT / "src/smb3_agent/tasks/checkpoint_1_1.py",
    REPOSITORY_ROOT / "src/smb3_agent/tasks/enter_1_1.py",
    REPOSITORY_ROOT / "src/smb3_agent/tasks/load_checkpoint_1_1.py",
    REPOSITORY_ROOT / "src/smb3_agent/tasks/run_1_1_script.py",
    REPOSITORY_ROOT / "src/smb3_agent/tasks/start_game.py",
)


def test_workflow_uses_required_unix_runner_triggers_and_canonical_gate() -> None:
    assert WORKFLOW_PATH.is_file(), f"canonical CI workflow is missing: {WORKFLOW_PATH}"
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert re.search(r"push:\s+branches:\s+- main", workflow)
    assert "workflow_dispatch:" in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "macos-latest" not in workflow
    assert "self-hosted" not in workflow
    assert "PYTHON=.venv/bin/python scripts/validate_phase0.sh" in workflow
    assert "uv sync --locked --all-extras" in workflow


def test_workflow_is_read_only_bounded_and_uses_immutable_house_pins() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    action_refs = re.findall(r"^\s*uses:\s*([^\s#]+)", workflow, flags=re.MULTILINE)

    assert re.search(r"permissions:\s+contents: read", workflow)
    assert "persist-credentials: false" in workflow
    assert "timeout-minutes: 20" in workflow
    assert 'CI: "true"' in workflow
    assert "python-version: \"3.11\"" in workflow
    assert 'version: "0.9.10"' in workflow
    assert "enable-cache: true" in workflow
    assert "cache-dependency-glob: uv.lock" in workflow
    assert "python -m pip install" not in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "fail-on-severity: moderate" in workflow
    assert CHECKOUT_PIN in action_refs
    assert SETUP_PYTHON_PIN in action_refs
    assert SETUP_UV_PIN in action_refs
    assert DEPENDENCY_REVIEW_PIN in action_refs
    assert action_refs
    assert all(re.search(r"@[0-9a-f]{40}$", action_ref) for action_ref in action_refs)


def test_workflow_has_no_live_gameplay_or_artifact_steps() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8").lower()

    forbidden = (
        ".nes",
        "fceux",
        "game-file",
        "smb3_game_file",
        "savestate",
        "goal run",
        "command run",
        "upload-artifact",
    )
    assert all(token not in workflow for token in forbidden)


def test_dependabot_covers_locked_python_and_actions_dependencies() -> None:
    dependabot = DEPENDABOT_PATH.read_text(encoding="utf-8")

    assert dependabot.count("interval: weekly") == 2
    assert "package-ecosystem: uv" in dependabot
    assert "package-ecosystem: github-actions" in dependabot
    assert dependabot.count("directory: /") == 2


def test_canonical_gate_covers_complete_rom_free_surface() -> None:
    gate = GATE_PATH.read_text(encoding="utf-8")
    required = (
        "git grep -nI -E '[[:blank:]]+$'",
        "git diff --check",
        "git diff --cached --check",
        "bash -n scripts/validate_phase0.sh",
        '"${python_bin}" -m ruff check src tests scripts/security_check.py',
        '"${python_bin}" scripts/security_check.py',
        '"${python_bin}" -m pytest -q',
        "goal validate data/goals/world_8_double_whistle.yaml",
        "segment validate",
        "data/segments/world_8_double_whistle.yaml",
        "--goal world_8_double_whistle",
        "goal status world_8_double_whistle",
        "lab ui-render --output",
        "mktemp -d",
        "trap cleanup_route_lab EXIT",
    )

    assert all(token in gate for token in required)
    assert gate.index("ruff check") < gate.index("pytest")
    assert gate.index("pytest") < gate.index("goal validate")
    assert gate.index("goal validate") < gate.index("segment validate")
    assert gate.index("segment validate") < gate.index("goal status")
    assert gate.index("goal status") < gate.index("lab ui-render")


def test_removed_legacy_ssot_paths_do_not_return() -> None:
    cli = CLI_PATH.read_text(encoding="utf-8")
    lab = LAB_PATH.read_text(encoding="utf-8")
    commands = COMMANDS_PATH.read_text(encoding="utf-8")
    catalog = CATALOG_PATH.read_text(encoding="utf-8")
    lab_ui = LAB_UI_PATH.read_text(encoding="utf-8")

    for command in (
        '"fceux-world-1-' + 'king"',
        '"propose-' + 'variant"',
        '"run-' + 'variant"',
        '"compare-' + 'variant"',
        '"promote-' + 'variant"',
    ):
        assert command not in cli
    for symbol in (
        "def propose_variant(",
        "def run_variant(",
        "def compare_variant(",
        "def promote_variant(",
    ):
        assert symbol not in lab
    for symbol in (
        "REVIEW_LATEST_FAILED_RE",
        "CONTINUE_AFTER_LIFE_LOSS_RE",
        'action="review_latest_failed"',
        'action="set_recovery_policy"',
        "recovery_policy: str | None",
    ):
        assert symbol not in commands
    assert 'build_default_catalog_registry(' in catalog
    assert 'CatalogRegistry((MarioCatalogProvider()' not in cli
    assert 'CatalogRegistry((*base' not in lab_ui


def test_repository_cleanup_keeps_docs_lean_linked_and_current() -> None:
    retired_paths = (
        "docs/attempt-lab.md",
        "docs/implementation-plan.md",
        "docs/validation-gates.md",
        "docs/world-1-lab-guide.md",
        "data/lab/codex-task-template.yaml",
        "data/lab/issue-ledger-template.yaml",
        "data/lab/note-template.yaml",
        "data/lab/session-template.yaml",
        "data/lab/variant-proposal-template.yaml",
        "data/routes/scripts/world_1_1_tail_from_stairs.yaml",
        "data/routes/scripts/world_1_1_to_late_pipe.yaml",
        "scripts/fceux_1_1_runner.lua",
        "scripts/fceux_probe.lua",
    )
    assert len(README_PATH.read_text(encoding="utf-8").splitlines()) < 180
    assert all(not (REPOSITORY_ROOT / path).exists() for path in retired_paths)

    markdown_files = (README_PATH, *sorted((REPOSITORY_ROOT / "docs").glob("*.md")))
    missing_links: list[tuple[Path, str]] = []
    for source in markdown_files:
        for target in re.findall(r"\[[^]]+\]\(([^)#]+)", source.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("/"):
                continue
            if not (source.parent / target).resolve().exists():
                missing_links.append((source, target))
    assert missing_links == []


def test_root_readme_reports_current_product_and_execution_boundaries() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    final_campaign = FINAL_CAMPAIGN_PATH.read_text(encoding="utf-8")
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")

    for required in (
        "# Game Companion",
        "uv sync --locked --all-extras",
        "PYTHON=.venv/bin/python scripts/validate_phase0.sh",
        "GAME_COMPANION_EXPERIMENTAL_ROOT",
        "inspection-only",
        "http://127.0.0.1:8765/",
        "`/mario`",
        "`/stardew`",
        "`/onboarding`",
        "`/lab`",
    ):
        assert required in readme
    assert "# Game Companion — Mario Adapter" not in readme
    assert "execution_enabled: false" in final_campaign
    assert "status: v2_14_campaign_entry_contract_ready" in final_campaign
    assert CAMPAIGN_ENTRY_SCHEMA_PATH.is_file()
    assert "Status: **in progress" not in roadmap


def test_public_documentation_omits_legacy_game_acquisition_language() -> None:
    markdown_files = (README_PATH, *sorted((REPOSITORY_ROOT / "docs").glob("*.md")))
    forbidden = re.compile(r"\b(?:rom|roms|snes)\b|\.nes\b", flags=re.IGNORECASE)

    for source in markdown_files:
        assert forbidden.search(source.read_text(encoding="utf-8")) is None, source


def test_runtime_docs_match_configuration_persistence_and_public_stardew_boundary() -> None:
    runtime = RUNTIME_DOC_PATH.read_text(encoding="utf-8")
    stardew = STARDEW_GUIDE_PATH.read_text(encoding="utf-8")
    experimental = EXPERIMENTAL_ADAPTERS_PATH.read_text(encoding="utf-8")
    final_campaign = FINAL_CAMPAIGN_PATH.read_text(encoding="utf-8")

    assert 'os.environ.get("GAME_COMPANION_EXPERIMENTAL_ROOT")' in experimental
    for setting in (
        "SMB3_GAME_FILE",
        "GAME_COMPANION_EXPERIMENTAL_ROOT",
        "PYTHON",
        "STARDEW_REGRESSION_SAVE",
    ):
        assert setting in runtime
    for path in (
        "artifacts/live-observation/",
        "artifacts/run-library/",
        "artifacts/learning/",
        "artifacts/product-session/",
        "artifacts/companion/",
        "artifacts/stardew-operator/",
        "artifacts/scenarios/",
        "artifacts/session-metrics/",
        "artifacts/unattended-regression/",
        "artifacts/campaigns/",
    ):
        assert path in runtime
    assert "inspection-only" in stardew
    assert "do not select or copy a save" in stardew.lower()
    assert "execution_enabled: false" in final_campaign
    assert "not a deployed job or generic CLI runner" in runtime


def test_gate_forbids_generated_evidence_game_assets_caches_and_metadata() -> None:
    gate = GATE_PATH.read_text(encoding="utf-8")

    for token in (
        "artifacts/*",
        "data/attempts/*",
        "data/screenshots/*",
        "data/variants/*.yaml",
        "public/assets/local/*",
        "*.nes",
        "*.fds",
        "*.sav",
        "*.state",
        "*.fc?",
        "*.fm2",
        "*.pyc",
        "__pycache__/*",
        ".pytest_cache/*",
        "*.egg-info/*",
    ):
        assert token in gate


def test_legacy_mednafen_results_do_not_persist_or_log_accessibility_permission() -> None:
    for module_path in LEGACY_MEDNAFEN_RESULT_MODULES:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        persisted_keys = {
            key.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Dict)
            for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        assert "accessibility_trusted" not in persisted_keys


def test_linux_dependency_surface_excludes_darwin_only_packages() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    normalized = {dependency.split(";", 1)[0].split(">=", 1)[0].lower(): dependency for dependency in dependencies}

    assert "numpy" in normalized
    assert "opencv-python" not in normalized
    assert "pynput" not in normalized
    for package in ("mss", "pyautogui", "pyobjc"):
        assert package in normalized
        assert "sys_platform == 'darwin'" in normalized[package]


def _run_cli_in_fresh_process(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    code = f"""
import sys
sys.argv = {['smb3_agent', *arguments]!r}
from smb3_agent.cli import main
main()
macos_modules = {MACOS_MODULES!r}
loaded = any(name in sys.modules for name in macos_modules)
print(f"macos_modules_loaded={{str(loaded).lower()}}")
"""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_importing_cli_does_not_load_macos_backend() -> None:
    code = f"""
import sys
import smb3_agent.cli
macos_modules = {MACOS_MODULES!r}
loaded = any(name in sys.modules for name in macos_modules)
print(f"macos_modules_loaded={{str(loaded).lower()}}")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "macos_modules_loaded=false" in result.stdout


@pytest.mark.parametrize(
    "arguments",
    (
        ["goal", "validate", "data/goals/world_8_double_whistle.yaml"],
        [
            "segment",
            "validate",
            "data/segments/world_8_double_whistle.yaml",
            "--goal",
            "world_8_double_whistle",
        ],
        ["goal", "status", "world_8_double_whistle"],
        ["lab", "ui-render", "--output", "{output}"],
        ["companion", "catalog-status"],
        ["companion", "render", "--output", "{output}"],
    ),
)
def test_rom_free_cli_commands_do_not_load_macos_backend(
    arguments: list[str], tmp_path: Path
) -> None:
    resolved_arguments = [
        str(tmp_path / "route-lab.html") if argument == "{output}" else argument
        for argument in arguments
    ]
    result = _run_cli_in_fresh_process(resolved_arguments)

    assert result.returncode == 0, result.stderr
    assert "macos_modules_loaded=false" in result.stdout


def test_mednafen_command_fails_explicitly_before_import_on_linux() -> None:
    code = f"""
import sys
sys.platform = "linux"
sys.argv = ["smb3_agent", "probe", "mednafen", "--game-file", "unused.nes"]
from smb3_agent.cli import main
try:
    main()
except SystemExit as exc:
    print(f"exit_code={{exc.code}}")
macos_modules = {MACOS_MODULES!r}
loaded = any(name in sys.modules for name in macos_modules)
print(f"macos_modules_loaded={{str(loaded).lower()}}")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "exit_code=2" in result.stdout
    assert "macos_modules_loaded=false" in result.stdout
    assert "supported only on macOS" in result.stderr
