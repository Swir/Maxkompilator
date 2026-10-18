# Maxkompilator 1.0 qualification

The release continues the existing repository and preserves the original v6, v7
and v8 handoff changes. Its defined scope is tracked in `progress.json` using the
original 100-point weights. Final aggregate CI qualification is still pending.

## What is delivered

The Windows application contains `Maxkompilator.exe`, `MaxkompilatorCLI.exe` and
their shared `_internal` directory. Extract and retain the entire directory.
The original multicolor 3D icon is unchanged. Technical documentation is English;
the interface, diagnostic messages and user-facing report are Polish.

The engine detects Python, .NET and Android projects, checks their tools, plans
and executes builds, validates output, records hashes, and handles cancellation
and timeouts. Profiles select application metadata, icons and bundled data.
Exact tool pins, adapter API v1 and a versioned remote-worker protocol complete
the defined extensibility foundations. See `EXTENSIONS.md` and `REMOTE_WORKER.md`.

## Actual qualification

All local records below are under `evidence/windows-2026-10-18/`.

| Area | Evidence and result |
|---|---|
| Engine and integrations | `unittest-v1.log`: 200 tests, 196 passed, four platform-specific skips |
| Final Windows GUI | `packaged-gui/qualification.json`: version 1.0.0, two independent relocated launches, ten checks and five compiled CLI workers per launch; all passed |
| Interactive Windows interface | `interactive-gui.json`: rc1 interface reviewed through real Windows controls; diagnostics, actual self-contained WinForms build, runtime success, readable labels and original icon; closed and reopened successfully |
| Python profile | `profile-qualification.json`: actual PE metadata and all seven icon payloads match; bundled resource runs; two Python 3.12.14 / PyInstaller 6.22.3 builds have identical hashes for all 56 files |
| CI Python profile | `ci-profile/profile-qualification.json`: same checks with the current Python 3.12.10 profile; 56 identical payload files across two builds |
| No installed Python | `ci-profile/python-free-windows.json`: two successful launches in a Windows Server Core container, no Python commands, executable installation or registry entries; both hashes match the profiled EXE |
| Container identity | `ci-profile/container-image.json`: Windows Server Core LTSC 2022, digest `sha256:593cf4a5ef08cfff00a03637e45eba073b8fe9dc90b80af4449bc5f427c7cdcd`; networking disabled during qualification |
| .NET console | `dotnet-build-report.json` and `dotnet-qualification.json`: real self-contained Windows publication, 188 files, copied outside source and run successfully |
| .NET desktop | `desktop-qualification.json` and `interactive-desktop-build.json`: actual WinForms window painted, timer executed, resource read, successful exit; 465 published files with WindowsDesktop runtime |
| Android | `apk-build-report.json`, `aab-build-report.json`, `android-qualification.json`: real Gradle APK/AAB, SDK manifest and certificate verification, independent bundletool 1.18.2 validation, APK installed and launched twice on API 36 emulator |

The Python-free container result is from CI job 117747360918 in run 39151908070;
that job passed, but the whole run failed on the Android SDK 37 output change.
The final source fixes that compatibility issue and is awaiting a complete rerun.
The local Sandbox trial was blocked by existing App Control policy; that policy
was left unchanged. The independent container test supplied the required evidence.

## Distribution boundaries

The portable application includes its runtime; compiling another project requires
the project's own tools and dependencies. Native Python applications target a
compatible runner. Actual native builds cover Windows x64, Linux x64 and macOS
ARM64; additional CPU selections have contract tests, not universal binary builds.

The included APK is a debug build. The AAB is an unsigned debug bundle, validated
as such; it is not a production-signed store release. Production signing, additional
language adapters and installers remain future scope. The remote protocol is
qualified through real local processes; deployment to a user's SSH host requires
that host's credentials, known-host entry and toolchain.

Original handoff integrity and the earlier 78-point integration checkpoint remain
documented in `INTEGRATION_2026-10-18.md`; those historical statements do not replace
the later evidence recorded here. No previous development schedule was resumed.
