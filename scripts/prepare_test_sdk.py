"""Prepare the GenVM runtime archive that direct mode tests load.

Direct mode (gltest 0.29.2) tries to download a release asset named
``genvm-universal.tar.xz`` from the pinned GenVM release. That asset name no longer
exists, so a clean machine cannot run the tests. genvm-linter 0.11.0 downloads the
same archive under its versioned name, so this script links or copies the already
resolved archive into the directory direct mode looks at.

Nothing installed is modified and no contract source is touched.

Usage:
    python scripts/prepare_test_sdk.py
    python scripts/prepare_test_sdk.py --version v0.3.0-rc7
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_VERSION = "v0.3.0-rc7"


def archive_name(version: str) -> str:
    return f"genvm-universal-{version}.tar.xz"


def cache_dir() -> Path:
    return Path.home() / ".cache" / "gltest-direct"


def linter_cache_dir() -> Path:
    return Path.home() / ".cache" / "genvm-linter"


def download_with_linter(version: str) -> Path:
    """Ask genvm-lint to fetch the archive, then return the path it wrote."""
    target = linter_cache_dir() / archive_name(version)
    if target.exists():
        return target

    print(f"fetching {version} through genvm-lint")
    result = subprocess.run(
        ["genvm-lint", "download", "--version", version],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit("genvm-lint download failed")
    if not target.exists():
        raise SystemExit(f"expected {target} after download")

    return target


def link_into_direct_cache(source: Path) -> Path:
    destination = cache_dir() / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()

    try:
        os.link(source, destination)
        print(f"linked: {destination} -> {source}")
    except OSError:
        try:
            destination.symlink_to(source)
            print(f"symlinked: {destination} -> {source}")
        except OSError:
            shutil.copy2(source, destination)
            print(f"copied: {destination} <- {source}")

    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    args = parser.parse_args()

    expected = cache_dir() / archive_name(args.version)
    if expected.exists():
        print(f"already in place: {expected}")
        return

    source = download_with_linter(args.version)
    link_into_direct_cache(source)


if __name__ == "__main__":
    main()
