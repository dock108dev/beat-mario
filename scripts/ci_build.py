"""Build from an export containing only versionable inputs, then import a fresh wheel."""

import argparse
import json
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import sys


def run(*args, **kwargs):
    subprocess.run(args, check=True, timeout=300, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="gc-ci-build-") as directory:
        temp = Path(directory)
        source = temp / "source"
        source.mkdir()
        files = (
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
            )
            .decode()
            .split("\0")
        )
        for name in sorted(set(files) - {""}):
            path = root / name
            if not path.is_file():
                continue
            if path.is_symlink():
                raise RuntimeError(f"Unexpected source symlink: {name}")
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        output = temp / "package"
        run("uv", "build", "--no-sources", "--out-dir", str(output), cwd=source)
        run("uv", "venv", "--python", sys.executable, str(temp / "env"))
        python = str(temp / "env/bin/python")
        requirements = temp / "runtime.txt"
        run(
            "uv",
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
            cwd=source,
            stdout=subprocess.DEVNULL,
        )
        run(
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--require-hashes",
            "-r",
            str(requirements),
        )
        (wheel,) = output.glob("*.whl")
        run("uv", "pip", "install", "--python", python, "--no-deps", str(wheel))
        run(
            python,
            "-I",
            "-c",
            "import smb3_agent.minecraft_memory, smb3_agent.minecraft_bridge, smb3_agent.minecraft_build, smb3_agent.minecraft_design, smb3_agent.lab_ui",
            cwd=temp,
        )
        sizes = {
            p.name: p.stat().st_size
            for p in output.iterdir()
            if p.suffix in (".gz", ".whl")
        }
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "sha": os.environ.get("GITHUB_SHA"),
                        "sizes_bytes": sizes,
                        "baseline": None,
                    },
                    indent=2,
                )
                + "\n"
            )
        summary = (
            "\n## Fresh export build\n\n"
            + "\n".join(
                f"- {name}: {size} bytes" for name, size in sorted(sizes.items())
            )
            + "\n\nWheel imports passed. This is not the signed macOS application; no comparable size baseline.\n"
        )
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
                stream.write(summary)
        print(summary)


if __name__ == "__main__":
    main()
