"""Qualify the real hello-android outputs with bundletool and an optional device.

Only --serial opts into installing and launching the example on that device.
This records debug-build evidence, never Play Store or release-key approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET


PACKAGE = "com.swir.maxkompilator.fixture"
MARKER = "MAXKOMPILATOR_ANDROID_RUNTIME_OK"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def read_artifact(report_path: Path, kind: str) -> tuple[dict, dict]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["status"] != "built" or report["project"]["kind"] != "android":
        raise ValueError(f"Expected a successful real Android build: {report_path}")
    task = ":app:assembleDebug" if kind == "apk" else ":app:bundleDebug"
    if not any(step["returncode"] == 0 and task in step["command"] for step in report["steps"]):
        raise ValueError(f"Missing successful Gradle {task} execution")
    artifacts = [item for item in report["artifacts"] if item["format"] == kind]
    if len(artifacts) != 1:
        raise ValueError(f"Expected exactly one {kind} example artifact")
    artifact = artifacts[0]
    if digest(Path(artifact["path"])) != artifact["sha256"]:
        raise ValueError(f"Changed {kind} bytes after the build")
    return report, artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk-report", type=Path, required=True)
    parser.add_argument("--aab-report", type=Path, required=True)
    parser.add_argument("--bundletool", type=Path, required=True)
    parser.add_argument("--java", default="java")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", help="Explicit device to install and launch the example on")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = {"status": "running", "scope": "hello-android debug example", "checks": [],
                "device": {"status": "not_run"}, "release_signing": "not_configured_or_qualified"}

    def run(command: list[str], timeout: int = 120) -> str:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, check=False)
        output = result.stdout + result.stderr
        evidence["checks"].append({"command": command, "returncode": result.returncode,
                                   "output": output[-16000:]})
        if result.returncode:
            raise RuntimeError(f"Command failed: {command[0]}\n{output[-2000:]}")
        return output

    try:
        apk_report, apk = read_artifact(args.apk_report, "apk")
        aab_report, aab = read_artifact(args.aab_report, "aab")
        if not apk["verified"] or apk["package"] != PACKAGE or apk["variant"] != "debug":
            raise ValueError("APK manifest and signing qualification did not pass")
        if aab.get("signature_status") not in {"unsigned", "jar_signed"}:
            raise ValueError("AAB signing state was not inspected")
        evidence.update(apk_sha256=apk["sha256"], aab_sha256=aab["sha256"],
                        apk_run_id=apk_report["run_id"], aab_run_id=aab_report["run_id"],
                        aab_signature_status=aab["signature_status"],
                        bundletool_sha256=digest(args.bundletool))
        tool = [args.java, "-jar", str(args.bundletool.resolve())]
        run([*tool, "validate", f"--bundle={aab['path']}"])
        manifest_text = run([*tool, "dump", "manifest", f"--bundle={aab['path']}", "--module=base"])
        manifest = ET.fromstring(manifest_text)
        application = manifest.find("application")
        if (manifest.get("package") != PACKAGE
                or manifest.get(ANDROID + "versionCode") != str(apk["version_code"])
                or manifest.get(ANDROID + "versionName") != apk["version_name"]
                or application is None or application.get(ANDROID + "debuggable") != "true"):
            raise ValueError("Decoded AAB manifest does not match the debug APK")
        evidence["bundletool_validation"] = "passed"
        evidence["bundle_manifest"] = {"package": PACKAGE, "version_code": apk["version_code"],
                                       "version_name": apk["version_name"], "debuggable": True}
        if args.serial:
            adb = [args.adb, "-s", args.serial]
            if run([*adb, "shell", "getprop", "sys.boot_completed"]).strip() != "1":
                raise ValueError("The selected Android device has not completed boot")
            api = run([*adb, "shell", "getprop", "ro.build.version.sdk"]).strip()
            install = run([*adb, "install", "-r", apk["path"]])
            if "Success" not in install:
                raise ValueError("APK installation was not confirmed")
            launches = []
            for _ in range(2):
                start = run([*adb, "shell", "am", "start", "-W", "-S", "-n", PACKAGE + "/.MainActivity"])
                if "Status: ok" not in start or "Error:" in start:
                    raise ValueError("Android did not confirm activity launch")
                pid = run([*adb, "shell", "pidof", PACKAGE]).strip()
                if not pid.isdecimal():
                    raise ValueError("The launched application has no unique live PID")
                deadline = time.monotonic() + 15
                while True:
                    logs = run([*adb, "logcat", "-d", "--pid=" + pid, "-s", "MaxkompilatorFixture:I", "*:S"])
                    if MARKER in logs:
                        break
                    if time.monotonic() >= deadline:
                        raise ValueError("Application resource/runtime marker missing")
                    time.sleep(0.5)
                launches.append({"pid": pid, "resource_marker": MARKER, "status": "passed"})
            evidence["device"] = {"status": "passed", "serial": args.serial, "api": api,
                                  "installation": "passed", "launches": launches}
        evidence["status"] = "passed"
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["error"] = str(exc)
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in evidence.items() if key != "checks"}, indent=2))


if __name__ == "__main__":
    main()
