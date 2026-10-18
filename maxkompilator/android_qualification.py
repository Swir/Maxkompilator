"""Qualify a real Gradle debug APK using its metadata and Android SDK tools.

The checksum comparison binds the *copied* artifact to the original Gradle
output.  Gradle's output-metadata.json binds the package and variant to the
specific APK.  aapt and apksigner independently validate the compiled Android
manifest and the actual APK signature.  No test of installation or launch is
claimed by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Callable

from .models import BuildPlan, MaxkompilatorError


_PACKAGE = re.compile(r"^package:\s+name='([^']+)'\s+versionCode='(\d+)'\s+versionName='([^']*)'", re.MULTILINE)
_CERT = re.compile(r"Signer #\d+ certificate SHA-256 digest:\s*([0-9a-fA-F]{64})(?![0-9a-fA-F])")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\Z")
_MAX_METADATA_BYTES = 1024 * 1024


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _build_tools(sdk: Path) -> tuple[Path, Path]:
    """Select a matching aapt executable and signer JAR from one SDK version."""
    build_tools = sdk.resolve() / "build-tools"
    if not build_tools.is_dir():
        raise MaxkompilatorError("Missing Android SDK build-tools directory.")

    def version_key(path: Path) -> tuple[int, ...]:
        # Prefer numerically newer tools (35.0.0 > 9.0.0), not lexicographic.
        return tuple(int(n) for n in re.findall(r"\d+", path.name))

    for directory in sorted(build_tools.iterdir(), key=version_key, reverse=True):
        if not directory.is_dir():
            continue
        aapt = directory / ("aapt.exe" if os.name == "nt" else "aapt")
        signer_jar = directory / "lib" / "apksigner.jar"
        if aapt.is_file() and signer_jar.is_file():
            return aapt.resolve(), signer_jar.resolve()
    raise MaxkompilatorError("Android SDK needs aapt and lib/apksigner.jar from the same build-tools version.")


def _parse_badging(result: dict) -> tuple[str, int, str, bool]:
    # run_command streams output and retains only its last 30 lines.  The
    # manifest/package lines often precede hundreds of resource lines; use the
    # separately captured matching lines instead of trusting output_tail.
    matches = "\n".join(result.get("matching_lines", ()))
    if not matches:
        matches = result.get("output_tail", "")
    package_match = _PACKAGE.search(matches)
    if package_match is None:
        raise MaxkompilatorError("aapt did not report an Android manifest package and version.")
    package, version_code, version_name = package_match.groups()
    if not _IDENTIFIER.fullmatch(package):
        raise MaxkompilatorError("Compiled APK has an invalid package identifier.")
    if "application-debuggable" not in matches.splitlines():
        raise MaxkompilatorError("Compiled APK is not marked debuggable, but a debug variant was requested.")
    return package, int(version_code), version_name, True


def _source_and_metadata(plan: BuildPlan, output_dir: Path, artifact: dict) -> tuple[Path, dict, dict]:
    root = plan.project.root.resolve(strict=True)
    copied = Path(artifact["path"]).resolve(strict=True)
    copied_root = output_dir.resolve(strict=True) / "artifacts"
    if not copied.is_relative_to(copied_root):
        raise MaxkompilatorError("APK was not copied from the Gradle app output into the report directory.")
    relative = copied.relative_to(copied_root)
    if (len(relative.parts) < 6 or relative.parts[:4] != ("app", "build", "outputs", "apk")
            or relative.suffix.lower() != ".apk" or relative.parts[4] != "debug"):
        raise MaxkompilatorError("APK path must originate from app/build/outputs/apk/<variant>/.")
    source = root / relative
    if source.is_symlink() or not source.resolve(strict=True).is_relative_to(root):
        raise MaxkompilatorError("Original Android artifact is an unsafe symlink or outside the project.")
    if not source.is_file() or _digest(source) != _digest(copied):
        raise MaxkompilatorError("Copied APK differs from the Gradle-produced APK.")
    if _digest(copied) != artifact.get("sha256"):
        raise MaxkompilatorError("APK checksum in build report does not match the saved artifact.")
    metadata_file = source.parent / "output-metadata.json"
    if not metadata_file.is_file() or metadata_file.stat().st_size > _MAX_METADATA_BYTES:
        raise MaxkompilatorError("Missing or oversized Gradle output-metadata.json.")
    if metadata_file.is_symlink() or not metadata_file.resolve(strict=True).is_relative_to(root):
        raise MaxkompilatorError("Gradle output metadata must remain inside the project.")
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise MaxkompilatorError("Gradle output-metadata.json is invalid JSON.") from exc
    if not isinstance(metadata, dict) or metadata.get("variantName") != "debug":
        raise MaxkompilatorError("Gradle metadata does not identify the requested debug variant.")
    elements = metadata.get("elements")
    if not isinstance(elements, list):
        raise MaxkompilatorError("Gradle metadata does not list the produced APK.")
    matching = [element for element in elements
                if isinstance(element, dict) and element.get("outputFile") == copied.name]
    if len(matching) != 1:
        raise MaxkompilatorError("Gradle metadata must reference the exact APK filename once.")
    return copied, metadata, matching[0]


def qualify_debug_apk(
    plan: BuildPlan,
    output_dir: Path,
    artifact: dict,
    sdk: Path,
    run_tool: Callable[[list[str]], dict],
) -> dict:
    """Return verified APK metadata, or raise without reporting a build success.

    `run_tool` must execute a command without a shell and support cancellation,
    timeouts, and matching-line capture for aapt's manifest lines.
    """
    if plan.project.kind != "android" or plan.format != "apk" or artifact.get("format") != "apk":
        raise MaxkompilatorError("APK validation requires a compiled Android APK plan.")
    if not any(":app:assembleDebug" in step.command for step in plan.steps):
        raise MaxkompilatorError("APK was not produced by the approved Gradle :app:assembleDebug task.")
    copied, metadata, element = _source_and_metadata(plan, output_dir, artifact)
    aapt, signer_jar = _build_tools(sdk)
    inspection = run_tool([str(aapt), "dump", "badging", str(copied)])
    if inspection.get("returncode") != 0:
        raise MaxkompilatorError("Android SDK aapt could not validate the compiled APK manifest.")
    package, code, name, _ = _parse_badging(inspection)
    if metadata.get("applicationId") != package:
        raise MaxkompilatorError("Compiled APK package differs from Gradle output metadata.")
    if type(element.get("versionCode")) is not int or element["versionCode"] != code:
        raise MaxkompilatorError("Compiled APK versionCode differs from Gradle output metadata.")
    if element.get("versionName") is not None and element["versionName"] != name:
        raise MaxkompilatorError("Compiled APK versionName differs from Gradle output metadata.")
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")) if java_home else "java"
    signature = run_tool([
        java, "-jar", str(signer_jar), "verify", "--verbose", "--print-certs", str(copied)
    ])
    if signature.get("returncode") != 0:
        raise MaxkompilatorError("Android apksigner rejected the compiled APK signature.")
    signatures = "\n".join(signature.get("matching_lines", ())) + "\n" + signature.get("output_tail", "")
    certs = sorted(set(fingerprint.lower() for fingerprint in _CERT.findall(signatures)))
    if not certs:
        raise MaxkompilatorError("Android apksigner returned no signer certificate SHA-256 fingerprint.")
    return {
        "verified": True,
        "verification": "gradle_debug_metadata+aapt_manifest+apksigner_signature; device_install_not_tested",
        "variant": "debug",
        "package": package,
        "version_code": code,
        "version_name": name,
        "signer_cert_sha256": certs,
        "manifest_check": inspection,
        "signature_check": signature,
    }
