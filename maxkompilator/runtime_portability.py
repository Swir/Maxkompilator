"""Relocate published .NET applications before attempting a runtime qualification.

Running a binary with its working directory elsewhere is *not* sufficient:
it can still load resources from the publish tree inside the checkout.
This module stages all published bytes in an unrelated temporary directory,
verifies every copied file against a pre-copy SHA-256 inventory, and supplies
evidence for the build report.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil

from .models import MaxkompilatorError


@dataclass(frozen=True)
class StagedRuntime:
    executable: Path
    source_sha256: str
    staged_sha256: str
    copied_files: int


def _digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def _inventory(directory: Path) -> dict[str, str]:
    """Hash all regular files, including target bytes of internal file symlinks.

    A snapshot of just the apphost is insufficient: the published DLLs and
    assets are equally important to what the app will execute and display.
    """
    hashes: dict[str, str] = {}
    for path in directory.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        # Source symlinks were checked by stage_dotnet_runtime. A copied tree
        # is checked separately below to reject any unexpected link.
        if not path.is_file():
            raise MaxkompilatorError(f"Unsupported .NET runtime file: {path}")
        hashes[path.relative_to(directory).as_posix()] = _digest(path)
    return hashes


def stage_dotnet_runtime(publish_directory: Path, executable: Path, destination_root: Path) -> StagedRuntime:
    """Copy a self-contained published app to a location outside the project.

    Do not run a single relocated EXE against old adjacent dependencies.
    Reject symlinks resolving outside the generated publish tree.
    Record both host hashes and verify *all* relocated runtime files against
    their original bytes before executing the relocated process.
    """
    source = publish_directory.resolve(strict=True)
    original = executable.resolve(strict=True)
    if not source.is_dir() or not original.is_file() or original.parent != source:
        raise MaxkompilatorError(".NET runtime must be an apphost directly inside its publish directory.")
    root = destination_root.resolve()
    if root == source or root.is_relative_to(source) or source.is_relative_to(root):
        raise MaxkompilatorError(".NET runtime staging must use a disjoint directory.")
    if not root.is_dir():
        raise MaxkompilatorError(".NET runtime staging destination does not exist.")
    for item in source.rglob("*"):
        if item.is_symlink():
            try:
                actual = item.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise MaxkompilatorError(f"Invalid .NET publish symlink: {item}") from exc
            if not actual.is_relative_to(source):
                raise MaxkompilatorError(".NET publish symlink points outside its output directory.")
            if actual.is_dir():
                raise MaxkompilatorError(".NET publish directory symlinks cannot be copied safely.")
    relocated = root / "publish"
    if relocated.exists() or relocated.is_symlink():
        raise MaxkompilatorError(".NET temporary publish destination is already occupied.")
    snapshot = _inventory(source)
    source_digest = snapshot[original.relative_to(source).as_posix()]
    try:
        shutil.copytree(source, relocated, symlinks=False)
        target = relocated / original.name
        if not target.is_file() or target.is_symlink():
            raise MaxkompilatorError(".NET staged apphost is missing or not a regular file.")
        # A symlink appearing during a copy must not survive the operation.
        # It could otherwise redirect the runtime back into the source tree.
        if any(path.is_symlink() for path in relocated.rglob("*")):
            raise MaxkompilatorError(".NET staged publish contains an unsafe symlink.")
        copied = _inventory(relocated)
        if copied != snapshot:
            raise MaxkompilatorError(".NET staged publish contents differ from the original SHA-256 snapshot.")
        return StagedRuntime(
            executable=target,
            source_sha256=source_digest,
            staged_sha256=copied[original.name],
            copied_files=len(copied),
        )
    except BaseException:
        shutil.rmtree(relocated, ignore_errors=True)
        raise
