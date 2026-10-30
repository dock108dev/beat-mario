"""Run checksum-pinned actionlint on supported CI/local review platforms."""

import hashlib
import platform
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen

VERSION = "1.7.12"
CHECKSUMS = {
    ("Linux", "x86_64"): (
        "linux_amd64",
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    ),
    ("Darwin", "arm64"): (
        "darwin_arm64",
        "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
    ),
}


def main():
    target, expected = CHECKSUMS[(platform.system(), platform.machine())]
    url = f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}/actionlint_{VERSION}_{target}.tar.gz"
    with tempfile.TemporaryDirectory(prefix="gc-actionlint-") as folder:
        archive = Path(folder) / "tool.tar.gz"
        with urlopen(url, timeout=60) as response:
            payload = response.read(32 * 1024 * 1024)
        if hashlib.sha256(payload).hexdigest() != expected:
            raise SystemExit("actionlint checksum mismatch")
        archive.write_bytes(payload)
        with tarfile.open(archive) as packed:
            member = packed.extractfile("actionlint")
            if member is None:
                raise SystemExit("actionlint binary missing")
            binary = Path(folder) / "actionlint"
            binary.write_bytes(member.read())
        binary.chmod(0o700)
        # ShellCheck is not implicitly supplied by the host: shell syntax is a separate gate.
        subprocess.run([str(binary), "-shellcheck=", "-color"], check=True)


if __name__ == "__main__":
    main()
