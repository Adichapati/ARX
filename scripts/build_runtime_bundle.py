#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DEFAULT_OUTPUT = DIST / "arx-runtime.zip"

INCLUDE_PREFIXES = (
    "dashboard/",
    "scripts/",
)

INCLUDE_EXACT = {
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "install.sh",
    "install.ps1",
    "install.bat",
    "requirements.txt",
    "main.py",
    "prompts/gemma-minecraft-commands.md",
    "app/minecraft_server/server.properties",
    "app/minecraft_server/start.sh",
    "app/minecraft_server/start.bat",
}

BUNDLE_SIZE_WARN_BYTES = 95 * 1024 * 1024

EXCLUDE_NAMES = {
    "install_BACKUP_574244.ps1",
    "install_BASE_574244.ps1",
    "install_LOCAL_574244.ps1",
    "install_REMOTE_574244.ps1",
}


def tracked_files() -> list[str]:
    out = subprocess.check_output(["git", "-C", str(ROOT), "ls-files"], text=True)
    files = []
    for raw in out.splitlines():
        rel = raw.strip()
        if not rel or rel in EXCLUDE_NAMES:
            continue
        if rel in INCLUDE_EXACT or rel.startswith(INCLUDE_PREFIXES):
            files.append(rel)
    return sorted(files)


def build_bundle(output: Path) -> tuple[int, str, int]:
    files = tracked_files()
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in files:
            zf.write(ROOT / rel, rel)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return len(files), digest, output.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Build lean ARX bootstrap runtime bundle.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output zip path (default: dist/arx-runtime.zip)")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    count, digest, size = build_bundle(output)

    print(f"Wrote {output}")
    print(f"Files: {count}")
    print(f"Size: {size} bytes")
    print(f"SHA256: {digest}")
    if size >= BUNDLE_SIZE_WARN_BYTES:
        print("WARNING: runtime bundle is approaching GitHub's 100MB file limit", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
