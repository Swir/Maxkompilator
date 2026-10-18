"""Verify copied Android App Bundle integrity and JAR signing evidence.

The debug Gradle task does not guarantee a signed AAB. An unsigned bundle
remains a build artifact, NOT a qualified release or installable APK. This
validator does not claim to decode the binary Android manifest or install an
app. Independent bundletool/device qualification is still required.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import zlib
from typing import Callable
import zipfile

from .models import BuildPlan, MaxkompilatorError

_FINGERPRINT = re.compile(r"\bSHA256:\s*((?:[a-fA-F0-9]{2}:){31}[a-fA-F0-9]{2})(?![a-fA-F0-9])")
_MAX_ZIP_MEMBERS = 100000
_MAX_UNCOMPRESSED = 8 * 1024**3


def _sha256(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            hash_.update(block)
    return hash_.hexdigest()


def _java_tool(name: str) -> str:
    home = os.environ.get("JAVA_HOME")
    if home:
        executable = Path(home) / "bin" / (name + (".exe" if os.name == "nt" else ""))
        if not executable.is_file():
            raise MaxkompilatorError(f"JAVA_HOME does not contain {name}; install a complete JDK.")
        return str(executable)
    return name


def _check_bundle_contents(bundle: Path) -> None:
    try:
        with zipfile.ZipFile(bundle) as archive:
            infos = archive.infolist()
            if len(infos) > _MAX_ZIP_MEMBERS:
                raise MaxkompilatorError("AAB archive contains too many entries.")
            names: set[str] = set()
            expanded = 0
            for info in infos:
                name = info.filename
                if name in names:
                    raise MaxkompilatorError("AAB archive contains duplicate entry names.")
                names.add(name)
                pieces = name.split("/")
                if (not name or name.startswith("/") or "\\" in name or "\x00" in name
                        or any(part in {"", ".", ".."} for part in pieces[:-1])
                        or any(part in {".", ".."} for part in pieces)
                        or re.match(r"^[A-Za-z]:", name)):
                    raise MaxkompilatorError("AAB archive contains an unsafe entry path.")
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise MaxkompilatorError("AAB archive contains a symlink entry.")
                expanded += info.file_size
                if expanded > _MAX_UNCOMPRESSED:
                    raise MaxkompilatorError("AAB archive exceeds the uncompressed-size safety limit.")
            required = ("BundleConfig.pb", "base/manifest/AndroidManifest.xml")
            if any(name not in names or archive.getinfo(name).file_size == 0 for name in required):
                raise MaxkompilatorError("AAB lacks nonempty BundleConfig.pb or base manifest.")
            # Stream every file through the ZIP checksum verifier: a central
            # directory alone does not establish integrity of its members.
            corrupt = archive.testzip()
            if corrupt:
                raise MaxkompilatorError(f"AAB archive contains a corrupt entry: {corrupt}.")
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError, zlib.error) as exc:
        raise MaxkompilatorError("Invalid or unreadable Android App Bundle archive.") from exc


def _output(result: dict) -> str:
    return "\n".join(result.get("matching_lines", ())) + "\n" + result.get("output_tail", "")


def qualify_debug_aab(
    plan: BuildPlan,
    output_dir: Path,
    artifact: dict,
    run_tool: Callable[[list[str], Path], dict],
) -> dict:
    """Qualify an actual Gradle bundle as signed/unsigned (no device claims).

    Files must be byte-for-byte identical to their copied report versions;
    JDK jarsigner checks cryptographic entries rather than trusting META-INF.
    """
    if plan.project.kind != "android" or plan.format != "aab" or artifact.get("format") != "aab":
        raise MaxkompilatorError("AAB validation requires an Android bundle build plan.")
    if not any(":app:bundleDebug" in step.command for step in plan.steps):
        raise MaxkompilatorError("AAB does not originate from :app:bundleDebug.")
    source_root = plan.project.root.resolve(strict=True)
    copied_root = (output_dir.resolve(strict=True) / "artifacts")
    copied_raw = Path(artifact["path"])
    if copied_raw.is_symlink():
        raise MaxkompilatorError("Copied AAB must not be a symbolic link.")
    copied = copied_raw.resolve(strict=True)
    if not copied.is_relative_to(copied_root):
        raise MaxkompilatorError("AAB was not saved to the build report artifact directory.")
    relative = copied.relative_to(copied_root)
    if (len(relative.parts) != 6 or relative.parts[:4] != ("app", "build", "outputs", "bundle")
            or relative.parts[4] != "debug" or relative.suffix.lower() != ".aab"):
        raise MaxkompilatorError("AAB must originate in app/build/outputs/bundle/debug/.")
    source = source_root / relative
    if source.is_symlink() or not source.resolve(strict=True).is_relative_to(source_root):
        raise MaxkompilatorError("Original AAB is an unsafe symlink or outside the project.")
    if not source.is_file() or not copied.is_file() or _sha256(copied) != _sha256(source):
        raise MaxkompilatorError("Copied AAB differs from the Gradle-produced AAB.")
    if _sha256(copied) != artifact.get("sha256"):
        raise MaxkompilatorError("AAB SHA-256 does not match the build report.")
    _check_bundle_contents(copied)

    # Older Windows JDK launchers mangle non-ANSI argv paths. A native cwd and
    # ASCII filename preserve Unicode project paths without OS locale changes.
    with tempfile.TemporaryDirectory(prefix='.aab-check-', dir=output_dir) as temporary:
        cwd = Path(temporary)
        staged = cwd / 'bundle.aab'
        shutil.copyfile(copied, staged)
        if _sha256(staged) != artifact['sha256']:
            raise MaxkompilatorError('AAB changed while staging signature verification.')
        return _check_signature(cwd, run_tool)


def _check_signature(cwd: Path, run_tool: Callable[[list[str], Path], dict]) -> dict:

    # JDK diagnostics are localized by the host. The parsed protocol needs a
    # stable locale on Polish Windows and other non-English workers.
    locale = ['-J-Duser.language=en', '-J-Duser.country=US']
    jar_check = run_tool([_java_tool("jarsigner"), *locale, "-verify", 'bundle.aab'], cwd)
    output = _output(jar_check)
    if jar_check.get("returncode") != 0:
        raise MaxkompilatorError("JDK jarsigner rejected the AAB signature or contents: " + output[-2000:])
    if "jar is unsigned." in output:
        return {
            "verified": False,
            "variant": "debug",
            "signature_status": "unsigned",
            "verification": "gradle_debug_provenance+zip_structure; AAB_unsigned; manifest_and_device_not_tested",
            "signature_check": jar_check,
        }
    if "jar verified." not in output:
        raise MaxkompilatorError("jarsigner did not confirm a verified JAR signature.")
    if "unsigned entries" in output.lower():
        raise MaxkompilatorError("AAB has unsigned entries; its whole payload is not integrity-protected.")
    certificate_check = run_tool([_java_tool("keytool"), *locale, "-printcert", "-jarfile", 'bundle.aab'], cwd)
    if certificate_check.get("returncode") != 0:
        raise MaxkompilatorError("keytool could not read the AAB signing certificate.")
    certs = sorted({digest.replace(":", "").lower() for digest in _FINGERPRINT.findall(_output(certificate_check))})
    if not certs:
        raise MaxkompilatorError("No SHA-256 signing certificate fingerprint was obtained for the AAB.")
    return {
        "verified": False,
        "signature_verified": True,
        "variant": "debug",
        "signature_status": "jar_signed",
        "signer_cert_sha256": certs,
        "verification": "partial:gradle_debug_provenance+zip_crc+jarsigner_signature; bundle_manifest_device_store_not_tested",
        "signature_check": jar_check,
        "certificate_check": certificate_check,
    }
